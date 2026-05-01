# Release Notes - v2026.05.01

**Release Date:** 2026-05-01  
**Tag:** v2026.05.01  
**Status:** Stable

## Overview

This release adds the Rust-backed lemma frequency pipeline from the
`feature/rust-lemma-freq` branch and documents the operational workflow around
it. The main linguistic-processing output format is unchanged; the release adds
a derived component product that aggregates lemma counts from existing
linguistic-processing JSONL outputs.

The release also updates the shared cookbook submodule, refreshes dependency
lock files, adds project-level agent guidance, and improves README guidance for
GNU Make usage on macOS.

## Linguistic Processing

- No intentional schema change to the main `sents` / `tsents` linguistic JSONL
  output.
- The existing `RUN_VERSION_LINGPROC` default remains `v2-0-0` unless a selected
  config file overrides it.
- `configs/config-lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3.mk` remains
  available for the historical `v1-0-3` run configuration.

## Lemma Frequencies

### Added

- New Rust streaming counter in `lemmafreq/aggregate_lemma_frequencies.rs`.
- New Cargo project metadata and lock file under `lemmafreq/`.
- New Python S3/local orchestration CLI in `lib/s3_lemmafreq.py`.
- New Make targets in `cookbook-repo-addons/lemmafreq.mk`.
- New detailed documentation in `README-LEMMAFREQ.md`.
- New local fixture in `test/lemmafreq/sample.jsonl`.

### Behavior

- The Rust worker reads linguistic-processing JSONL and counts lemmas from both
  `sents` and `tsents`.
- It filters by language, UPOS tag, and minimum lemma length.
- It accepts both historical `tok` arrays and current `tokens` arrays.
- It uses lemma field `l` when present and non-empty, otherwise falls back to
  surface token field `t`.
- Lemmas are lowercased before counting.
- Malformed JSONL lines are skipped with warnings rather than aborting the whole
  stream.

### Targets

Newspaper/language compute targets:

```sh
make compute-lemma-frequencies-BL/AATA-en
make compute-lemma-frequencies-de
make compute-lemma-frequencies-fr
make compute-lemma-frequencies-en
make compute-lemma-frequencies-lb
make compute-all-lemma-frequencies
```

Language-level aggregation targets:

```sh
make aggregate-lemma-frequencies-de
make aggregate-lemma-frequencies
```

On macOS, run these targets with `remake` or `gmake`.

### Output Paths and Format

Lemma frequency outputs are written below:

```text
s3://<component-bucket>/lemma-freq/<run-id>/<language>/
```

Newspaper-level outputs follow this pattern:

```text
<NEWSPAPER>.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2
```

Language-level aggregated outputs follow this pattern:

```text
ALL.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2
```

The selection label is derived from:

- `LEMMAFREQ_POS_TAGS`, default `PROPN,NOUN`
- `LEMMAFREQ_MIN_LENGTH`, default `2`

This lets multiple lemma selections coexist under the same run and language
prefix.

### Recompute Granularity

Lemma frequency compute targets operate at newspaper/language granularity. They
do not track individual year-level S3 linguistic-processing inputs as Make
prerequisites. If a year-level input is replaced on S3, delete the corresponding
newspaper/language lemma frequency output and `.wip` marker before rerunning the
target.

## Orchestration

- The root `Makefile` now includes `cookbook-repo-addons/lemmafreq.mk`.
- `help` output includes lemma frequency setup, compute, and aggregate targets.
- The Make include order was adjusted so newspaper list configuration is
  available to generated lemma frequency targets.
- The cookbook submodule was updated through `v1.4.0-7-g1ddd10c`, bringing in
  centralized help output and recent S3/WIP orchestration improvements.
- `S3_BUCKET_REBUILT` and `S3_BUCKET_LINGPROC` defaults are aligned with current
  final bucket names through the cookbook update.

## Dependencies and Models

- `Pipfile`, `Pipfile.lock`, and `requirements.txt` were refreshed.
- `jq` and the editable local `impresso-cookbook` package remain part of the
  Python environment.
- The lemma frequency counter adds a Rust/Cargo requirement for lemma frequency
  targets only.
- No bundled spaCy model update is intended in this release.

## Documentation

- `README.md` now documents lemma frequency targets, current processing options,
  output format, validation commands, and macOS GNU Make usage.
- `README-LEMMAFREQ.md` documents the new lemma frequency architecture,
  configuration, input/output format, recomputation behavior, and operational
  examples.
- `AGENT.md` documents project-specific guidance for future coding agents.
- `RELEASE_PROCESS.md` documents this repository's release workflow.

## Compatibility and Migration

- Existing linguistic-processing outputs remain compatible with downstream
  consumers.
- The new lemma frequency product is additive.
- Operators who want lemma frequency outputs must build the Rust binary and run
  the new compute/aggregate targets.
- Downstream consumers should treat the lemma selection label in filenames as
  part of the product identity.

## Validation

The following checks were run before preparing this release:

```sh
python3 -m py_compile lib/spacy_linguistic_processing.py lib/s3_lemmafreq.py
cargo test --manifest-path lemmafreq/Cargo.toml
remake help
```

Results:

- Python syntax check passed.
- Rust tests passed: 5 passed, 0 failed.
- `remake help` completed and showed the new lemma frequency targets.

Full S3 pipeline execution was not run as part of release preparation because it
requires live credentials and selected production inputs.

## Known Issues

- Full pipeline verification remains environment-dependent because it requires
  S3 credentials and access to Impresso buckets.

## Links

- Repository: https://github.com/impresso/impresso-linguistic-processing
- Branch prepared: `feature/rust-lemma-freq`
- Suggested comparison: `v2025.01.02...v2026.05.01`
