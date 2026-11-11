#!/usr/bin/env python3
"""Check that rebuilt texts can be reconstructed from a lingproc file.

The lingproc output has no explicit space-after property. Token offsets `o`
point into the rebuilt text, and spaCy emits every whitespace other than a
single space after a token as a token of its own (newlines, repeated spaces).
So the text is reconstructed by placing each token at its offset and filling
each gap between tokens with one space; the space-after flag of a token is
implied by whether such a gap follows it.

For every content item in the lingproc file, the script checks:

- each token's text equals the rebuilt text at its offset,
- offsets increase and tokens do not overlap,
- every gap between tokens is exactly one space,
- the reconstruction equals the rebuilt text (`ft` for `sents`, the title for
  `tsents`), apart from leading and trailing whitespace that spaCy drops.

Both the current output (`ci_id`, `tokens`) and the older one (`id`, `tok`)
are accepted.

Rebuilt items without a lingproc record (for example too short or too long)
are counted but not checked.

Usage:
    python lib/check_lingproc_reconstruction.py REBUILT.jsonl.bz2 LINGPROC.jsonl.bz2
Both paths may be local or s3:// URLs (credentials from .env).
Exit status is 1 if any item fails.
"""

import argparse
import collections
import json
import logging
import sys
from typing import Any, Dict, Iterator, List, Optional, Tuple

import dotenv
import smart_open

from impresso_cookbook import get_s3_client

log = logging.getLogger(__name__)


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    """Yield JSON objects from a local or S3 JSONL file (compression by suffix)."""
    transport_params = {"client": get_s3_client()} if path.startswith("s3://") else {}
    with smart_open.open(path, "r", transport_params=transport_params) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def sent_tokens(sent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a sentence's tokens (`tokens`, or `tok` in older lingproc output)."""
    return sent.get("tokens", sent.get("tok", []))


def reconstruct(sents: List[Dict[str, Any]]) -> Tuple[str, int, List[bool]]:
    """Rebuild a text from tokens and offsets, filling gaps with one space.

    Returns the reconstruction, the offset of its first character, and the
    implied space-after flag for each token.
    """
    tokens = [tok for sent in sents for tok in sent_tokens(sent)]
    if not tokens:
        return "", 0, []
    start = tokens[0]["o"]
    parts = []
    space_after = []
    pos = start
    for i, tok in enumerate(tokens):
        if tok["o"] > pos:
            parts.append(" " * (tok["o"] - pos))
        parts.append(tok["t"])
        pos = tok["o"] + len(tok["t"])
        nxt = tokens[i + 1]["o"] if i + 1 < len(tokens) else None
        space_after.append(nxt is not None and nxt > pos)
    return "".join(parts), start, space_after


def check_text(
    original: str, sents: List[Dict[str, Any]], max_errors: int = 3
) -> List[str]:
    """Return a list of problems found when reconstructing `original`."""
    problems: List[str] = []
    tokens = [tok for sent in sents for tok in sent_tokens(sent)]
    pos = None
    for tok in tokens:
        o, t = tok["o"], tok["t"]
        if original[o : o + len(t)] != t:
            problems.append(
                f"token {t!r} at {o} does not match text {original[o:o + len(t)]!r}"
            )
        if pos is not None:
            if o < pos:
                problems.append(f"token {t!r} at {o} overlaps previous token")
            elif o - pos > 1 or (o - pos == 1 and original[pos] != " "):
                problems.append(
                    f"gap {original[pos:o]!r} before token {t!r} at {o} is not one space"
                )
        pos = o + len(t)
        if len(problems) >= max_errors:
            return problems
    text, start, _ = reconstruct(sents)
    if text != original.strip() and text != original[start : start + len(text)]:
        problems.append("reconstruction differs from original text")
    elif original[:start].strip() or original[start + len(text) :].strip():
        problems.append("non-whitespace text outside the tokens")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("rebuilt", help="Rebuilt JSONL file (local or s3://)")
    parser.add_argument("lingproc", help="Lingproc JSONL file (local or s3://)")
    parser.add_argument(
        "--text-property", default="ft", help="Rebuilt full-text property (default ft)"
    )
    parser.add_argument(
        "--show", type=int, default=10, help="Failing items to print (default 10)"
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")
    dotenv.load_dotenv()

    rebuilt = {}
    for doc in read_jsonl(args.rebuilt):
        rebuilt[doc.get("id") or doc.get("ci_id")] = (
            doc.get(args.text_property) or "",
            doc.get("t") or doc.get("title") or "",
        )

    stats: collections.Counter = collections.Counter()
    shown = 0
    for doc in read_jsonl(args.lingproc):
        stats["LINGPROC-ITEMS"] += 1
        ci_id = doc.get("ci_id") or doc.get("id")
        if ci_id not in rebuilt:
            stats["MISSING-IN-REBUILT"] += 1
            continue
        full_text, title = rebuilt.pop(ci_id)
        for field, original in (("sents", full_text), ("tsents", title)):
            sents = doc.get(field) or []
            if not sents:
                continue
            stats[f"{field.upper()}-CHECKED"] += 1
            problems = check_text(original, sents)
            if problems:
                stats[f"{field.upper()}-FAILED"] += 1
                if shown < args.show:
                    shown += 1
                    print(f"{ci_id} {field}:", file=sys.stderr)
                    for p in problems:
                        print(f"  {p}", file=sys.stderr)
            else:
                stats[f"{field.upper()}-OK"] += 1
    stats["REBUILT-ITEMS-WITHOUT-LINGPROC"] = len(rebuilt)

    for key in sorted(stats):
        print(f"{key}: {stats[key]}")
    failed = stats["SENTS-FAILED"] + stats["TSENTS-FAILED"] + stats["MISSING-IN-REBUILT"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
