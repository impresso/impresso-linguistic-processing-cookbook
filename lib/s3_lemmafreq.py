#!/usr/bin/env python3
"""Compute lemma frequencies from linguistic-processing JSONL with a Rust worker."""

import argparse
import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence

import smart_open
from impresso_cookbook import (
    get_transport_params,
    parse_s3_path,
    setup_logging,
    yield_s3_objects,
)

LOG = logging.getLogger(__name__)


def iter_s3_jsonl_lines(s3_prefix: str, extension: str) -> Iterator[str]:
    """Yield JSONL lines from all matching S3 objects under a prefix."""
    bucket, prefix = parse_s3_path(s3_prefix)
    transport_params = get_transport_params(s3_prefix)
    matched = 0

    for file_key in sorted(yield_s3_objects(bucket, prefix)):
        if not file_key.endswith(extension):
            continue
        matched += 1
        uri = f"s3://{bucket}/{file_key}"
        LOG.info("Reading %s", uri)
        with smart_open.open(
            uri, "r", encoding="utf-8", transport_params=transport_params
        ) as infile:
            yield from infile

    LOG.info("Read %d matching files with extension %s", matched, extension)


def iter_local_jsonl_lines(paths: Sequence[str]) -> Iterator[str]:
    """Yield JSONL lines from local files supported by smart_open."""
    for path in paths:
        LOG.info("Reading %s", path)
        with smart_open.open(path, "r", encoding="utf-8") as infile:
            yield from infile


def log_stderr(stderr: Optional[Any]) -> None:
    """Forward Rust stderr into Python logging."""
    if stderr is None:
        return
    for line in stderr:
        LOG.info("lemmafreq: %s", line.rstrip())


def compute_with_rust(
    lines: Iterable[str],
    binary: str,
    language: str,
    pos_tags: str,
    min_length: int,
) -> Dict[str, int]:
    """Stream JSONL lines into the Rust binary and return its JSON result."""
    env = os.environ.copy()
    env.update(
        {
            "LANGUAGE": language,
            "POS_TAGS": pos_tags,
            "MIN_LENGTH": str(min_length),
        }
    )

    LOG.info(
        "Starting %s with LANGUAGE=%s POS_TAGS=%s MIN_LENGTH=%s",
        binary,
        language,
        pos_tags,
        min_length,
    )
    process = subprocess.Popen(
        [binary],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stderr_thread = threading.Thread(
        target=log_stderr, args=(process.stderr,), daemon=True
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
        raise RuntimeError(f"{binary} failed with exit code {return_code}")

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{binary} emitted invalid JSON") from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            f"{binary} emitted {type(result).__name__}, expected object"
        )

    LOG.info("Rust worker returned %d unique lemmas", len(result))
    return {str(key): int(value) for key, value in result.items()}


def parse_pos_tags(pos_tags: str) -> list[str]:
    return [tag for tag in pos_tags.replace(" ", ",").split(",") if tag]


def write_json(path: str, data: Dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with smart_open.open(tmp_path, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, ensure_ascii=False, sort_keys=True)
        outfile.write("\n")
    tmp_path.replace(output_path)


def read_json_object(uri: str) -> Dict[str, Any]:
    transport_params = get_transport_params(uri)
    with smart_open.open(
        uri, "r", encoding="utf-8", transport_params=transport_params
    ) as infile:
        data = json.load(infile)
    if not isinstance(data, dict):
        raise ValueError(f"{uri} contains {type(data).__name__}, expected object")
    return data


def frequency_payload(data: Dict[str, Any]) -> Dict[str, int]:
    freqs = data.get("freqs", data)
    if not isinstance(freqs, dict):
        raise ValueError("frequency payload must be an object")
    return {str(key): int(value) for key, value in freqs.items()}


def wrap_result(options: argparse.Namespace, freqs: Dict[str, int]) -> Dict[str, Any]:
    if options.raw_output:
        return freqs
    return {
        "newspaper": options.newspaper,
        "language": options.language,
        "pos_tags": parse_pos_tags(options.pos_tags),
        "min_length": options.min_length,
        "run_id": options.run_id,
        "freqs": freqs,
    }


def run_compute(options: argparse.Namespace) -> None:
    if options.s3_prefix:
        lines = iter_s3_jsonl_lines(options.s3_prefix, options.extension)
    else:
        lines = iter_local_jsonl_lines(options.input_file)

    freqs = compute_with_rust(
        lines,
        options.binary,
        options.language,
        options.pos_tags,
        options.min_length,
    )
    write_json(options.output, wrap_result(options, freqs))
    LOG.info("Wrote %s", options.output)


def iter_frequency_objects(
    s3_prefix: str, suffix: str
) -> Iterator[tuple[str, Dict[str, Any]]]:
    bucket, prefix = parse_s3_path(s3_prefix)
    for file_key in sorted(yield_s3_objects(bucket, prefix)):
        if not file_key.endswith(suffix) or os.path.basename(file_key).startswith(
            "ALL_"
        ):
            continue
        uri = f"s3://{bucket}/{file_key}"
        LOG.info("Merging %s", uri)
        yield uri, read_json_object(uri)


def run_merge(options: argparse.Namespace) -> None:
    merged: Dict[str, int] = {}
    source_count = 0

    if options.s3_prefix:
        objects = iter_frequency_objects(options.s3_prefix, options.suffix)
    else:
        objects = ((path, read_json_object(path)) for path in options.input_file)

    for _, data in objects:
        source_count += 1
        for lemma, count in frequency_payload(data).items():
            merged[lemma] = merged.get(lemma, 0) + count

    LOG.info("Merged %d files into %d unique lemmas", source_count, len(merged))
    output = (
        merged
        if options.raw_output
        else {
            "language": options.language,
            "pos_tags": parse_pos_tags(options.pos_tags),
            "min_length": options.min_length,
            "run_id": options.run_id,
            "source_count": source_count,
            "freqs": merged,
        }
    )
    write_json(options.output, output)
    LOG.info("Wrote %s", options.output)


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", required=True, help="Local JSON output path")
    parser.add_argument("--log-file", help="Optional log file path")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
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


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
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


def main(args: Optional[Sequence[str]] = None) -> None:
    options = parse_args(args)
    setup_logging(options.log_level, options.log_file, force=True)
    LOG.info("Arguments: %s", options)

    if options.command == "compute":
        run_compute(options)
    elif options.command == "merge":
        run_merge(options)
    else:
        raise AssertionError(f"Unhandled command {options.command}")


if __name__ == "__main__":
    main()
