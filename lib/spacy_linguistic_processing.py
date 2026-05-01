#!/usr/bin/env python3

"""
This script preprocesses text for topic modeling using precomputed language identification results.

Functions:
    initialize_validator: Initializes the schema validator.
    get_next_doc: Generates documents from a file line by line.
    output_doc: Outputs a document to the specified file.
    read_langident: Reads language identification results from a file.

Classes:
    LinguisticProcessing: Processes documents, adding linguistic annotations.

Usage example:
    python spacy_linguistic_processing.py --input path/to/input --output-path path/to/output
"""

import argparse
import collections
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, Generator, IO, Optional, Sequence
from pathlib import Path

import dotenv
import jsonschema
from jsonschema import Draft7Validator

import smart_open
import spacy

from impresso_cookbook import (
    keep_timestamp_only,
    parse_s3_path,
    get_s3_client,
    s3_file_exists,
    upload_file_to_s3,
    get_timestamp,
    have_same_md5,
)

dotenv.load_dotenv()


log = logging.getLogger(__name__)

SCHEMA_BASE_URI = (
    "https://impresso.github.io/impresso-schemas/json/linguistic_annotation/"
)

IMPRESSO_SCHEMA = "lingproc.v2.schema.json"


# TAG map for lb language processing
LB_TAG_MAP = {
    "$": "PUNCT",
    "ADJ": "ADJ",
    "AV": "ADV",
    "APPR": "ADP",
    "APPRART": "ADP",
    "D": "DET",
    "KO": "CONJ",
    "N": "NOUN",
    "P": "ADV",
    "TRUNC": "X",
    "AUX": "AUX",
    "V": "VERB",
    "MV": "VERB",
    "PTK": "PART",
    "INTER": "PART",
    "NUM": "NUM",
    "_SP": "SPACE",
}


def map_tag(tag: str, lang: str) -> str:
    """
    Maps a tag to the appropriate POS tag for the specified language.

    Args:
        tag (str): The tag to map.
        lang (str): The language code.

    Returns:
        str: The mapped tag.
    """
    if lang == "lb":
        return LB_TAG_MAP.get(tag, "X")
    return tag


def analyze_title_in_text(title: str, full_text: str) -> Dict[str, bool]:
    """Analyze the relationship between the title and the full text.

    Args:
        title: The title string
        full_text: The full text string

    Returns:
        Dict[str, bool]: Analysis results
    """
    ADVERTISEMENT = re.compile(
        r"""^
      \s* adv\. \s* \d+ \s* page \s* \d+ \s*
    | \s* publicité \s* \d+ page \s* \d+ \s*
    $""",
        flags=re.IGNORECASE + re.VERBOSE,
    )
    len_title = len(title)
    len_full_text = len(full_text)
    analysis = {
        "exact_prefix": False,
        "ellipsis": None,
        "alnum_prefix": None,
        "alnum_infix": None,
        "unknown": None,
        "title_longer": len_title > len_full_text,
        "advertisement": None,
    }
    # Check for "UNKNOWN" or "UNTITLED" in title
    if title.strip().upper() in {
        "UNKNOWN",
        "UNTITLED",
        "UNTITLED ARTICLE",
        "UNTITLED AD",
    }:
        analysis["unknown"] = True
        return analysis

    if re.match(ADVERTISEMENT, title):
        analysis["advertisement"] = True
        return analysis

    # Check for exact prefix match
    # there are rare cases where the actual title ends with ...
    # https://impresso-project.ch/app/issue/armeteufel-1911-06-04-a/view?p=1&articleId=i0010
    if full_text.startswith(title):
        analysis["exact_prefix"] = True
        return analysis

    # Check for ellipsis and remove if present
    if title.endswith("..."):
        analysis["ellipsis"] = True
        title = title[:-3]
        len_title = len(title)

    if full_text.startswith(title):
        analysis["exact_prefix"] = True
        return analysis

    # Check if title is longer than full text
    # We do not need to further analyze in this case
    if len_title > len_full_text:
        return analysis

    alphanum_title = "".join(c for c in title if c.isalnum())
    alphanum_text = "".join(c for c in full_text if c.isalnum())
    if alphanum_text.startswith(alphanum_title):
        analysis["alnum_prefix"] = True
        return analysis

    # Sometimes the actual title has a preceding smaller subtitle and therefore is not
    # the prefix of the full text. In order to not overmatch, we only test this if at
    # least one whitespace is present in the title and the title is at least 20
    # characters long
    if " " in title and len_title >= 20:
        if alphanum_title in alphanum_text:
            analysis["alnum_infix"] = True
            return analysis
    return analysis


def process_text_with_spacy(text: str, lang: str, nlp: spacy.language.Language) -> list:
    """Process text with spaCy and extract linguistic features.

    Args:
        text (str): Input text to process
        lang (str): Language code
        nlp (spacy.language.Language): Loaded spaCy model

    Returns:
        list: List of sentences with tokenization and linguistic annotations
    """
    doc = nlp(text)
    preprocessed_text = []
    tag_accessor = "tag_" if lang == "lb" else "pos_"

    for sent in doc.sents:
        preprocessed_sent = []
        for tok in sent:
            tok_dict = {
                "t": tok.text,
                "p": map_tag(getattr(tok, tag_accessor), lang),
                "o": tok.idx,
            }
            if tok.text != tok.lemma_:
                tok_dict["l"] = tok.lemma_

            if tok.ent_type_:
                tok_dict["e"] = f"{tok.ent_iob_}-{tok.ent_type_}"

            preprocessed_sent.append(tok_dict)

        preprocessed_text.append({"lg": lang, "tokens": preprocessed_sent})

    return preprocessed_text


def initialize_validator(
    schema_base_uri=SCHEMA_BASE_URI, schema=IMPRESSO_SCHEMA
) -> jsonschema.Draft7Validator:
    """
    Initializes the schema validator.
    """
    with smart_open.open(
        schema_base_uri + schema,
        "r",
    ) as f:
        schema = json.load(f)

    # Directly create the validator without a registry or a resolver
    validator = Draft7Validator(schema)
    return validator


def get_next_doc(
    infile: str, client: Optional[Any] = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Generates documents from a file line by line.

    Args:
        infile (str):a The path to the input file.
        client (Optional[Any]): The S3 client to use for reading the file.
            Defaults to None.

    Yields:
        Generator[Dict[str, Any], None,t None]: A generator yielding documents as
            dictionaries.
    """
    transport_params = {}
    if client is not None:
        transport_params = {"client": client}
    with smart_open.open(infile, "r", transport_params=transport_params) as instream:
        for line in instream:
            yield json.loads(line)


def output_doc(doc: Dict[str, Any], out_file: "IO[str]") -> None:
    """
    Outputs a document to the specified file.

    Args:
        doc (Dict[str, Any]): The document to output.
        out_file (IO[str]): The file object to write the document to.
    """
    print(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), file=out_file)


def read_langident(path: str, client: Optional[Any] = None) -> Dict[str, str]:
    """
    Reads language identification results from a file.

    Args:
        path (str): The (s3) path to the language identification file.
        client (Optional[Any]): The S3 client to use for reading the file.
    Returns:
        Dict[str, str]: A dictionary mapping document IDs to their identified languages.
    """

    result = {}
    transport_params = {}
    if client is not None:
        transport_params = {"client": client}

    with smart_open.open(
        path,
        "r",
        encoding="utf-8",
        transport_params=transport_params,
    ) as f:
        for line in f:
            try:
                contentitem = json.loads(line)
                result[contentitem["id"]] = contentitem.get("lg")
            except KeyError:
                log.error("Problem %s", line)
    return result


LANG2MODEL = {
    "de": "de_core_news_md",
    "fr": "fr_core_news_md",
    "fre": "fr_core_news_md",
    "en": "en_core_web_md",
    "lb": "./models/lb_model/model-best/",
    "es": "es_core_news_md",
}


class LinguisticProcessing:
    def __init__(self, args: argparse.Namespace):
        """
        Initializes the LinguisticProcessing class.

        Args:
            args (argparse.Namespace): The command line arguments.
        """
        self.args = args

        self.S3_CLIENT = (
            get_s3_client()
            if self.args.INPUT.startswith("s3://")
            or str(self.args.lid).startswith("s3://")
            else None
        )
        if not args.s3_output_dry_run:
            # Check if the output file already exists in S3 and avoid lengthy processing
            if self.args.quit_if_s3_output_exists and (
                s3out := self.args.s3_output_path
            ):
                if s3_file_exists(self.S3_CLIENT, s3out):
                    log.warning(
                        "%s exists. Exiting without processing %s",
                        s3out,
                        self.args.INPUT,
                    )
                    exit(3)
                else:
                    log.info("%s does not exist. Proceeding with processing.", s3out)

        self.language_proc_units: Dict[str, spacy.language.Language] = {}
        self.lang_ident_data: Dict[str, str] | None = (
            read_langident(self.args.lid, client=self.S3_CLIENT)
            if self.args.lid
            else None
        )
        self.model_versions: Dict[str, str] = {}  # Store model versions
        self.git_version = (
            self.args.git_version
            if self.args.git_version
            else os.environ.get("GIT_VERSION", "unknown")
        )
        if self.args.validate:
            self.schema_validator = initialize_validator()

        self.stats = collections.Counter()

    def create_lpu(self, lang: str) -> None:
        """
        Creates a language processing unit for the specified language.

        Args:
            lang (str): The language code.
        """
        lang2model = LANG2MODEL
        if lang not in self.language_proc_units and lang in lang2model:
            nlp = spacy.load(lang2model.get(lang, lang), disable=["parser"])
            nlp.add_pipe("sentencizer", first=True)
            nlp.max_length = self.args.max_doc_length + 1
            self.language_proc_units[lang] = nlp
            self.model_versions[lang] = (
                "spacy@"
                + spacy.__version__
                + ":"
                + nlp.meta["lang"]
                + "_"
                + nlp.meta["name"]
                + "@"
                + nlp.meta["version"]
                + ":"
                + "|".join(nlp.pipe_names)
            )
            log.info("LOADED PIPELINE %s %s", nlp, nlp.pipeline)
            log.info("model_id: %s", self.model_versions[lang])
        else:
            log.error("No model found for %s", lang)

    def process_doc(
        self,
        json_obj: Dict[str, Any],
        timestamp: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a single document, adding linguistic annotations.

        Args:
            json_obj (Dict[str, Any]): The document to process.
            timestamp (str): The current timestamp.

        Returns:
            Optional[Dict[str, Any]]: The processed document or None if processing
                fails.
        """
        docid = json_obj.get("ci_id", json_obj.get("ci_ref", json_obj["id"]))

        full_text = json_obj.get(self.args.text_property)
        if full_text is None:
            log.debug(
                "Full text property `%s` unavailable in `%s`",
                self.args.text_property,
                docid,
            )
            self.stats["CONTENT-ITEMS-NO-TEXT"] += 1
            return None

        full_text_len = len(full_text)

        title_text = json_obj.get("t", json_obj.get("title"))
        if title_text:
            self.stats["CONTENT-ITEMS-WITH-TITLE"] += 1
        else:
            self.stats["CONTENT-ITEMS-WITHOUT-TITLE"] += 1

        title_text_len = len(title_text) if title_text else 0

        text_len = full_text_len + title_text_len
        if text_len == 0:
            log.debug("Empty text: %s", docid)
            self.stats["CONTENT-ITEMS-EMPTY"] += 1
            return None
        elif text_len < self.args.min_doc_length:
            log.debug("Short text (%s chars): %s ", text_len, docid)
            self.stats["CONTENT-ITEMS-SHORT"] += 1
            return None
        elif text_len > self.args.max_doc_length:
            log.debug("Long text (%s chars): %s ", text_len, docid)
            self.stats["CONTENT-ITEMS-LONG"] += 1
            return None

        lang = None
        lid_path = "default"

        if self.args.language:
            lang = self.args.language
            self.stats["LANG-FROM-ARG"] += 1
        elif self.lang_ident_data:
            lang = self.lang_ident_data.get(docid)
            if lang:
                self.stats["LANG-FROM-LID"] += 1
                lid_path = self.args.lid
        if lang is None:
            lang = json_obj.get("lg")
            if lang:
                self.stats["LANG-FROM-DOC"] += 1
            else:
                self.stats["LANG-NONE"] += 1
                log.warning(
                    "Skipping %s. Language is None. Text: `%s`",
                    docid,
                    full_text[:50],
                )
                return None

        if lang not in LANG2MODEL:
            log.warning("No spacy model for language %s: content item: %s", lang, docid)
            return None

        if lang not in self.language_proc_units:
            self.create_lpu(lang)
        title_status = {}
        if title_text:
            title_status = analyze_title_in_text(title_text, full_text)
        if title_status.get("unknown"):
            self.stats["CONTENT-ITEMS-TITLE-unknown"] += 1
            title_text = ""

        self.stats["CONTENT-ITEMS-OK"] += 1
        preprocessed_text = []

        preprocessed_title = []
        if title_text:
            preprocessed_title = process_text_with_spacy(
                title_text, lang, self.language_proc_units[lang]
            )

        preprocessed_text = process_text_with_spacy(
            full_text, lang, self.language_proc_units[lang]
        )
        title_status = {k: v for k, v in title_status.items() if v is not None}
        for k, v in title_status.items():
            self.stats[f"TITLE-STATUS-{k}"] += 1
        result = {
            "ci_id": docid,
            "ts": timestamp,
            "tsents": preprocessed_title,
            "sents": preprocessed_text,
            "model_id": self.model_versions[lang],
            "lid_path": lid_path,
            "lingproc_git": self.git_version,
            "char_count": text_len,
            "min_chars": self.args.min_doc_length,
            "max_chars": self.args.max_doc_length,
            "title_status": title_status,
        }

        return result

    def run(self) -> None:
        """
        Runs the linguistic processing on all documents.
        """
        infile = self.args.INPUT
        outfile: str = self.args.output_path
        s3_outfile: str = self.args.s3_output_path
        timestamp: str = get_timestamp()
        collection: str = os.path.basename(infile).split("-")[0]
        year: str = infile.split("-")[-1][:4]

        total_doc_count = len(self.lang_ident_data) if self.lang_ident_data else 1
        newspaper = outfile.split("/")[-1].split(".")[0]
        start_time = time.time()
        processed_doc_count = 1
        log.info("Processing %s %s %s", infile, collection, year)

        with smart_open.open(outfile, "w") as out:
            # make sure that the file is not empty and in case of bz2 that it is a valid
            # file!
            out.write("")
            doc_iter = enumerate(get_next_doc(infile, client=self.S3_CLIENT), start=1)
            for i, json_obj in doc_iter:
                if json_obj is None:
                    continue
                processed_doc = self.process_doc(json_obj, timestamp)
                if self.args.validate and processed_doc is not None:
                    if not self.validate_document(processed_doc):
                        sys.exit(1)

                if processed_doc is not None:
                    output_doc(processed_doc, out)
                    processed_doc_count += 1
                    if processed_doc_count % 1000 == 0:
                        end_time = time.time()

                        log.info(
                            "Processed %d content items with content (total with"
                            " unprocessable: %d/%d in %s) in %d secs/1k content items",
                            processed_doc_count,
                            i,
                            total_doc_count,
                            newspaper,
                            round((end_time - start_time), 1),
                        )
                        start_time = end_time
        log.info(
            "Processed %d processable documents (total documents: %d)",
            processed_doc_count,
            i,
        )

        for k in sorted(self.stats):
            log.info("%s: %d", k, self.stats[k])
        log.info("File %s successfully processed locally.", infile)

        # Upload the output file to S3 if specified
        if not self.args.s3_output_dry_run and s3_outfile:
            upload_file_to_s3(self.S3_CLIENT, outfile, s3_outfile)

            if self.args.keep_timestamp_only:
                keep_timestamp_only(outfile)

    def upload_file_to_s3(self, local_file_path: str, s3_path: str) -> None:
        """Uploads a local file to an S3 bucket if it doesn't already exist and verifies
        the upload."""

        bucket, key = parse_s3_path(s3_path)
        if s3_file_exists(self.S3_CLIENT, bucket, key):
            log.warning(
                "The file s3://%s/%s already exists. Skipping upload.", bucket, key
            )
            return

        try:
            # Upload the file to S3
            log.info("Uploading %s to s3://%s/%s", local_file_path, bucket, key)
            self.S3_CLIENT.upload_file(local_file_path, bucket, key)
            log.info(
                "Successfully uploaded %s to s3://%s/%s", local_file_path, bucket, key
            )

            # Verify the upload by comparing MD5 checksums
            if have_same_md5(local_file_path, s3_path, self.S3_CLIENT):
                log.info("File %s successfully verified after upload.", local_file_path)
            else:
                log.error(
                    "MD5 checksum mismatch: local file %s != s3 file %s",
                    local_file_path,
                    s3_path,
                )
                raise ValueError("MD5 checksum mismatch after upload.")

        except FileNotFoundError:
            log.error("The file %s was not found.", local_file_path)
        except self.S3_CLIENT.exceptions.NoCredentialsError:
            log.error("Credentials not available.")
        except self.S3_CLIENT.exceptions.PartialCredentialsError:
            log.error("Incomplete credentials provided.")
        except Exception as e:
            log.error("An error occurred: %s", e)

    def validate_document(self, document: Dict[str, Any]) -> bool:
        """
        Validates a document against the schema.

        Args:
            document (Dict[str, Any]): The document to validate.

        Returns:
            bool: True if the document is valid, False otherwise.
        """
        try:
            self.schema_validator.validate(document)
            log.debug("Document %s is valid", document["ci_id"])
            return True
        except jsonschema.ValidationError as e:
            log.error("Validation error: %s", e)
            return False
        except jsonschema.SchemaError as e:
            log.error("Schema error: %s", e)
            return False


def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Configure logging with smart_open support.

    Args:
        log_level: Logging level as a string
        log_file: Path to the log file
    """

    class SmartFileHandler(logging.FileHandler):
        def _open(self):
            return smart_open.open(self.baseFilename, self.mode, encoding="utf-8")

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(SmartFileHandler(str(log_file), mode="w"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(filename)s:%(lineno)d %(levelname)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def parse_arguments(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        argparse.Namespace: Parsed arguments
    """
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(help="Path to impresso rebuilt file", dest="INPUT")
    parser.add_argument("--lid", help="Path to language identification file")
    parser.add_argument(
        "--language", help="Specify a language code to use for all items"
    )
    parser.add_argument(
        "-o", "--output-path", default="out.jsonl", help="Path to output file"
    )
    parser.add_argument(
        "--min-doc-length",
        type=int,
        default=50,
        help=(
            "Minimum document length (title together with full text) to process"
            " (default %(default)s)"
        ),
    )
    parser.add_argument(
        "--max-doc-length",
        type=int,
        default=50000,
        help=(
            "Maximum document length (title together with full text) to process"
            " (default %(default)s)"
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "validate final lang identification JSON against schema (default"
            " %(default)s)"
        ),
    )
    parser.add_argument(
        "--text-property",
        default="ft",
        help="Specify the JSON property that contains the full text (%(default)s)",
    )
    parser.add_argument(
        "--git-version",
        help=(
            "Set the git version to include in the output. If not set, the GIT_VERSION"
            " environment variable is used."
            "Normally the output of `git describe --tags --always` is used."
        ),
    )
    parser.add_argument(
        "--quit-if-s3-output-exists",
        action="store_true",
        help="Quit if the output file already exists in the specified S3 bucket",
    )
    parser.add_argument(
        "--s3-output-path",
        help=(
            "S3 path to upload the output file after processing or check if it already"
            " exists"
        ),
    )
    parser.add_argument(
        "--keep-timestamp-only",
        action="store_true",
        help=(
            "After uploading to S3, keep only the timestamp of the local output file"
            " for data efficiency. Defaults: %(default)s"
        ),
    )
    parser.add_argument(
        "--s3-output-dry-run",
        action="store_true",
        help=(
            "Dry run which suppresses all write operations to s3 and checks whether"
            " output files on s3 exist. Implies also unsetting --keep-timestamp-only"
            " and --quit-if-s3-output-exists flag."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument("-l", "--log-file", type=Path, help="Log file path")

    options = parser.parse_args(args)

    if options.s3_output_dry_run:
        options.keep_timestamp_only = False
        options.quit_if_s3_output_exists = False
    logging.info("Called with args: %s", options)
    return options


def main(args: Optional[Sequence[str]] = None) -> None:
    """Main function to run the processor.

    Args:
        args: Command-line arguments (uses sys.argv if None)
    """
    # Parse arguments
    options = parse_arguments(args)

    # Setup logging
    setup_logging(options.log_level, options.log_file)

    log.info("Called with args: %s", options)
    app = LinguisticProcessing(options)
    # Launching application...
    app.run()

    sys.exit(0)


if __name__ == "__main__":
    main()
