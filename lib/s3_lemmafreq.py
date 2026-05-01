#!/usr/bin/env python3
"""
Compute lemma frequencies from linguistic-processing JSONL with a Rust worker.

This command follows the local CLI conventions from ``lib/cli_TEMPLATE.py``:
argument parsing is kept separate from processing, logging is configured through
``impresso_cookbook.setup_logging()``, and the main workflow is encapsulated in a
processor class.

The script is intentionally repo-specific. S3 access, transport configuration,
and logging use ``impresso_cookbook`` helpers, while lemma counting is delegated
to the Rust ``aggregate_lemma_frequencies`` binary. JSON outputs ending in
``.bz2`` are compressed/decompressed by ``smart_open``.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from smart_open import open as smart_open  # type: ignore

from impresso_cookbook import (  # type: ignore
    get_transport_params,
    parse_s3_path,
    setup_logging,
    yield_s3_objects,
)

log = logging.getLogger(__name__)


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compute = subparsers.add_parser("compute", help="Compute lemma frequencies")
    add_common_options(compute)
    compute.add_argument("--s3-prefix", help="S3 prefix containing JSONL files")
    compute.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Local input file; may be repeated",
    )
    compute.add_argument(
        "--extension",
        default="jsonl.bz2",
        help="S3 object suffix to read",
    )
    compute.add_argument(
        "--binary",
        required=True,
        help="Path to aggregate_lemma_frequencies binary",
    )
    compute.add_argument("--newspaper", help="Newspaper identifier for metadata")

    merge = subparsers.add_parser("merge", help="Merge lemma frequency JSON files")
    add_common_options(merge)
    merge.add_argument("--s3-prefix", help="S3 prefix containing lemmafreq JSON files")
    merge.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Local lemmafreq JSON file; may be repeated",
    )
    merge.add_argument(
        "--suffix",
        default="lemmafreq.json",
        help="S3 object suffix to merge",
    )

    options = parser.parse_args(args)
    if options.command == "compute" and not (options.s3_prefix or options.input_file):
        parser.error("compute requires --s3-prefix or --input-file")
    if options.command == "merge" and not (options.s3_prefix or options.input_file):
        parser.error("merge requires --s3-prefix or --input-file")
    return options


def add_common_options(parser: argparse.ArgumentParser) -> None:
    """Add command-line options shared by compute and merge commands."""
    parser.add_argument("-o", "--output", required=True, help="Local JSON output path")
    parser.add_argument("--log-file", help="Optional log file path")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument("--language", default="de", help="Language code")
    parser.add_argument(
        "--pos-tags", default="PROPN,NOUN", help="Comma-separated POS tags"
    )
    parser.add_argument("--min-length", type=int, default=2, help="Minimum lemma length")
    parser.add_argument("--run-id", help="Cookbook run identifier")
    parser.add_argument(
        "--raw-output",
        action="store_true",
        help="Write the raw lemma frequency object without metadata",
    )


class LemmaFrequencyProcessor:
    """Processor for computing and merging lemma frequency JSON payloads."""

    def __init__(self, options: argparse.Namespace) -> None:
        """
        Initialize the processor with parsed command-line options.

        Args:
            options: Parsed command-line options.
        """
        self.options = options
        setup_logging(options.log_level, options.log_file, logger=log)

    def run(self) -> None:
        """Run the selected command."""
        if self.options.command == "compute":
            self.run_compute()
        elif self.options.command == "merge":
            self.run_merge()
        else:
            raise ValueError(f"Unhandled command {self.options.command}")

    def run_compute(self) -> None:
        """Compute lemma frequencies and write the result."""
        if self.options.s3_prefix:
            uris = self.list_s3_jsonl_uris(
                self.options.s3_prefix, self.options.extension
            )
            if not uris:
                raise RuntimeError(
                    "No input files found under "
                    f"{self.options.s3_prefix} with suffix {self.options.extension}"
                )
            lines = self.iter_jsonl_uris(uris)
        else:
            lines = self.iter_local_jsonl_lines(self.options.input_file)

        freqs = self.compute_with_rust(lines)
        self.write_json(self.options.output, self.wrap_result(freqs))
        log.info("Wrote %s", self.options.output)

    def run_merge(self) -> None:
        """Merge existing lemma frequency JSON objects."""
        merged: Dict[str, int] = {}
        source_count = 0

        if self.options.s3_prefix:
            objects = self.iter_frequency_objects(
                self.options.s3_prefix, self.options.suffix
            )
        else:
            objects = (
                (path, self.read_json_object(path)) for path in self.options.input_file
            )

        for _, data in objects:
            source_count += 1
            for lemma, count in self.frequency_payload(data).items():
                merged[lemma] = merged.get(lemma, 0) + count

        log.info("Merged %d files into %d unique lemmas", source_count, len(merged))
        output = (
            merged
            if self.options.raw_output
            else {
                "language": self.options.language,
                "pos_tags": self.parse_pos_tags(self.options.pos_tags),
                "min_length": self.options.min_length,
                "run_id": self.options.run_id,
                "source_count": source_count,
                "freqs": merged,
            }
        )
        self.write_json(self.options.output, output)
        log.info("Wrote %s", self.options.output)

    def list_s3_jsonl_uris(self, s3_prefix: str, extension: str) -> List[str]:
        """List matching JSONL S3 object URIs under a prefix."""
        bucket, prefix = parse_s3_path(s3_prefix)
        uris = []

        for file_key in sorted(yield_s3_objects(bucket, prefix)):
            if not file_key.endswith(extension):
                continue
            uris.append(f"s3://{bucket}/{file_key}")

        log.info("Found %d matching files with suffix %s", len(uris), extension)
        return uris

    def iter_jsonl_uris(self, uris: Sequence[str]) -> Iterator[str]:
        """Yield JSONL lines from local or S3 URIs."""
        for uri in uris:
            transport_params = get_transport_params(uri)
            log.info("Reading %s", uri)
            with smart_open(
                uri, "r", encoding="utf-8", transport_params=transport_params
            ) as infile:
                yield from infile

    def iter_local_jsonl_lines(self, paths: Sequence[str]) -> Iterator[str]:
        """Yield JSONL lines from local files."""
        for path in paths:
            log.info("Reading %s", path)
            with smart_open(
                path,
                "r",
                encoding="utf-8",
                transport_params=get_transport_params(path),
            ) as infile:
                yield from infile

    def compute_with_rust(self, lines: Iterable[str]) -> Dict[str, int]:
        """Stream JSONL lines into the Rust binary and return its JSON result."""
        env = os.environ.copy()
        env.update(
            {
                "LANGUAGE": self.options.language,
                "POS_TAGS": self.options.pos_tags,
                "MIN_LENGTH": str(self.options.min_length),
            }
        )

        log.info(
            "Starting %s with LANGUAGE=%s POS_TAGS=%s MIN_LENGTH=%s",
            self.options.binary,
            self.options.language,
            self.options.pos_tags,
            self.options.min_length,
        )
        process = subprocess.Popen(
            [self.options.binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        stderr_thread = threading.Thread(
            target=self.log_rust_stderr, args=(process.stderr,), daemon=True
        )
        stderr_thread.start()

        assert process.stdin is not None
        for line in lines:
            process.stdin.write(line)
            if not line.endswith("\n"):
                process.stdin.write("\n")
        process.stdin.close()

        assert process.stdout is not None
        stdout = process.stdout.read()
        return_code = process.wait()
        stderr_thread.join(timeout=5)

        if return_code != 0:
            raise RuntimeError(
                f"{self.options.binary} failed with exit code {return_code}"
            )

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{self.options.binary} emitted invalid JSON") from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                f"{self.options.binary} emitted {type(result).__name__}, "
                "expected object"
            )

        log.info("Rust worker returned %d unique lemmas", len(result))
        return {str(key): int(value) for key, value in result.items()}

    @staticmethod
    def log_rust_stderr(stderr: Optional[Any]) -> None:
        """Forward Rust stderr into Python logging."""
        if stderr is None:
            return
        for line in stderr:
            log.info("lemmafreq: %s", line.rstrip())

    def iter_frequency_objects(
        self, s3_prefix: str, suffix: str
    ) -> Iterator[tuple[str, Dict[str, Any]]]:
        """Yield lemma frequency JSON objects from an S3 prefix."""
        bucket, prefix = parse_s3_path(s3_prefix)
        for file_key in sorted(yield_s3_objects(bucket, prefix)):
            basename = os.path.basename(file_key)
            if (
                not file_key.endswith(suffix)
                or basename.startswith("ALL_")
                or basename.startswith("ALL.")
            ):
                continue
            uri = f"s3://{bucket}/{file_key}"
            log.info("Merging %s", uri)
            yield uri, self.read_json_object(uri)

    def wrap_result(self, freqs: Dict[str, int]) -> Dict[str, Any]:
        """Wrap raw lemma frequencies in cookbook metadata unless disabled."""
        if self.options.raw_output:
            return freqs
        return {
            "newspaper": self.options.newspaper,
            "language": self.options.language,
            "pos_tags": self.parse_pos_tags(self.options.pos_tags),
            "min_length": self.options.min_length,
            "run_id": self.options.run_id,
            "freqs": freqs,
        }

    @staticmethod
    def parse_pos_tags(pos_tags: str) -> list[str]:
        """Parse comma- or space-separated POS tags."""
        return [tag for tag in pos_tags.replace(" ", ",").split(",") if tag]

    @staticmethod
    def write_json(path: str, data: Dict[str, Any]) -> None:
        """Write JSON, using smart_open compression based on the path suffix."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
        payload = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        with smart_open(str(tmp_path), "wb") as outfile:
            outfile.write(payload)
        tmp_path.replace(output_path)

    @staticmethod
    def read_json_object(uri: str) -> Dict[str, Any]:
        """Read a JSON object, using smart_open compression based on the suffix."""
        transport_params = get_transport_params(uri)
        with smart_open(
            uri, "r", encoding="utf-8", transport_params=transport_params
        ) as infile:
            data = json.load(infile)
        if not isinstance(data, dict):
            raise ValueError(f"{uri} contains {type(data).__name__}, expected object")
        return data

    @staticmethod
    def frequency_payload(data: Dict[str, Any]) -> Dict[str, int]:
        """Extract and normalize the frequency payload from wrapped or raw data."""
        freqs = data.get("freqs", data)
        if not isinstance(freqs, dict):
            raise ValueError("frequency payload must be an object")
        return {str(key): int(value) for key, value in freqs.items()}


def main(args: Optional[List[str]] = None) -> None:
    """
    Main function to run lemma frequency processing.

    Args:
        args: Command-line arguments (uses sys.argv if None)
    """
    options = parse_arguments(args)
    processor = LemmaFrequencyProcessor(options)

    log.info("%s", options)
    processor.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"Processing error: {e}", exc_info=True)
        sys.exit(2)
