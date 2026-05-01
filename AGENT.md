# AGENT.md

## Purpose

This repository is the Impresso linguistic processing cookbook. It wires the
shared make-based cookbook helpers in `cookbook/` to a concrete pipeline for
spaCy-based linguistic annotation and lemma-frequency aggregation.

The main processing product is linguistic JSONL output with POS tags, NER tags,
lemmas, title sentences, model metadata, and run metadata. A secondary product
computes newspaper- and language-level lemma frequency distributions from those
linguistic outputs.

## Main Entry Points

- `Makefile`: top-level orchestration entry point.
- `cookbook/processing_lingproc.mk`: Make rules that run linguistic processing.
- `lib/spacy_linguistic_processing.py`: main spaCy processing script.
- `cookbook-repo-addons/lemmafreq.mk`: Make rules for lemma frequency products.
- `lib/s3_lemmafreq.py`: Python S3/local orchestration for lemma frequencies.
- `lemmafreq/aggregate_lemma_frequencies.rs`: Rust streaming lemma counter.
- `cookbook/`: shared Make/Python cookbook framework used by this project.

The `cookbook/AGENT.md` file documents the reusable cookbook layer. Prefer this
root file for project-level guidance.

## Tooling And Environment

- Python 3.11 is expected.
- The project normally uses `pipenv`, but local `venv/` or `.venv/`
  environments are also normal for local work.
- On macOS, use GNU Make via `remake` or `gmake`; `/usr/bin/make` is too old.
- Keep command examples and Makefile target names written as `make` in docs.
- S3 credentials come from environment variables or `.env`:
  `SE_ACCESS_KEY`, `SE_SECRET_KEY`, and `SE_HOST_URL`.

## Operational Model

- Inputs and outputs live on S3.
- Local files under `build.d/` are mostly stamps, logs, or transient outputs.
- Make targets use local stamp files to decide what should run.
- `python3 -m impresso_cookbook.local_to_s3` is the normal upload and WIP-marker
  helper. Do not replace it with raw `aws s3 cp` in recipes unless explicitly
  changing pipeline semantics.
- `.wip` objects are used to prevent concurrent workers from producing the same
  S3 target.

## Important Make Variables

- `CFG`: selects a run-specific Make config.
- `NEWSPAPER`: selected newspaper prefix, often including provider.
- `NEWSPAPER_HAS_PROVIDER`: whether newspaper IDs include a provider prefix.
- `NEWSPAPERS_TO_PROCESS_FILE`: list used by collection runs.
- `NEWSPAPER_JOBS`: parallel jobs within one newspaper.
- `COLLECTION_JOBS`: number of newspapers launched concurrently.
- `MAX_LOAD`: load limit for Make/GNU parallel.
- `LINGPROC_LANGIDENT_NEEDED`: whether lingproc depends on langident inputs.
- `RUN_ID_LINGPROC`: computed output run identifier.
- `LEMMAFREQ_POS_TAGS`, `LEMMAFREQ_MIN_LENGTH`: lemma frequency selection.

## Safe Working Rules

- Do not modify or commit secrets in `.env` or `.aws/credentials`.
- Treat untracked notebooks, sample JSONL files, compressed test inputs, and
  local visualization scripts as user state unless explicitly told otherwise.
- Do not delete `build.d/`, S3 stamps, local sample data, or WIP markers as a
  cleanup step unless the user explicitly requests it.
- Preserve S3 path conventions and stamp-file behavior when editing Make rules.
- When editing Make fragments, keep the existing style: documented user
  variables, double-colon target extension, and help text for public targets.
- Lemma frequency recomputation is newspaper/language level. If one year-level
  lingproc input changes, the corresponding newspaper/language lemmafreq output
  and WIP marker must be removed before recomputing.

## Practical Validation

Use the smallest checks that match the change:

```sh
python3 -m py_compile lib/spacy_linguistic_processing.py lib/s3_lemmafreq.py
cargo test --manifest-path lemmafreq/Cargo.toml
make help
```

On macOS, run the Make command through `remake` or `gmake`.

Full pipeline targets usually need live S3 credentials and network access, so
avoid running them casually during documentation or narrow code changes.
