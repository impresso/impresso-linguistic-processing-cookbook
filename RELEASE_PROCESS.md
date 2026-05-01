# Release Process Guide

This document describes how to prepare and publish releases for the Impresso
linguistic processing repository.

This repository is a processing pipeline, not a library-only project. A release
is a tagged repository snapshot that captures changes to:

- spaCy-based linguistic processing in `lib/spacy_linguistic_processing.py`,
- Make orchestration in `Makefile`, `cookbook/*.mk`, and
  `cookbook-repo-addons/*.mk`,
- lemma-frequency tooling in `lib/s3_lemmafreq.py` and `lemmafreq/`,
- dependency definitions in `Pipfile`, `Pipfile.lock`, and `requirements.txt`,
- bundled model assets under `models/`,
- run configuration files in `configs/`,
- operational documentation such as `README.md`, `AGENT.md`, and this file.

The release must make clear whether it changes the repository code, the
linguistic processing output contract, the default `RUN_ID_LINGPROC`, or any
derived component products such as lemma frequencies.

## Table of Contents

- [Release Workflow](#release-workflow)
- [Version Naming](#version-naming)
- [Preparing a Release](#preparing-a-release)
- [Release Notes](#release-notes)
- [Publishing a Release](#publishing-a-release)
- [Post-Release Tasks](#post-release-tasks)
- [Hotfix Releases](#hotfix-releases)
- [Checklist](#checklist)

## Release Workflow

### Overview

Releases follow these steps:

1. Prepare the repository state for release.
2. Review pipeline, dependency, cookbook, and configuration changes.
3. Update release documentation.
4. Write and commit release notes before tagging.
5. Open and merge a pull request into `main`.
6. Create an annotated git tag from the merged commit on `main`.
7. Publish a GitHub release from the committed release notes file.
8. Perform post-release verification.

The main rule is that release notes must be committed before the tag is created.
The tag, release notes, README release entry, and published GitHub release should
all refer to the same repository snapshot.

The normal path is therefore:

1. prepare release changes on a branch,
2. merge that branch through a pull request,
3. switch to the updated `main`,
4. tag the merged commit on `main`,
5. publish the GitHub release from that tag.

Creating a release directly from a feature branch should be treated as an
exception.

## Version Naming

There are two related version concepts in this repository:

- **Git release tags** identify repository snapshots.
- **Pipeline run versions** are Make variables such as `RUN_VERSION_LINGPROC`
  and are embedded in `RUN_ID_LINGPROC`.

Historical git tags include both date-based and pipeline-like names:

- `v1-0-2`
- `v2024.04.04`
- `v2024.11.24`
- `v2025.01.02`

For current repository releases, use date-based tags:

```text
vYYYY.MM.DD
```

Examples:

- `v2026.05.01`
- `v2026.06.15`

For pipeline run versions, keep the existing run-ID style used by Make:

```makefile
RUN_VERSION_LINGPROC ?= v2-0-0
```

If a release changes the linguistic output schema, default model set, or
processing semantics, update `RUN_VERSION_LINGPROC` intentionally and document
the resulting `RUN_ID_LINGPROC`, for example:

```text
lingproc-pos-spacy_v3.6.0-multilingual_v2-0-0
```

Use the same git tag string consistently in:

- the git tag,
- the release notes filename,
- the GitHub release title.

Use the same pipeline run version consistently in:

- `cookbook/paths_lingproc.mk` or selected `configs/*.mk`,
- `README.md` release notes,
- release notes operational guidance,
- any S3 output path examples affected by the change.

## Preparing a Release

### 1. Review the Changes

Inspect all commits and changed files since the previous release tag:

```bash
git log <previous-tag>..HEAD --oneline
git diff <previous-tag>..HEAD --stat
git diff <previous-tag>..HEAD --name-status
```

Focus especially on these areas:

- `Makefile`
- `README.md`
- `AGENT.md`
- `RELEASE_PROCESS.md`
- `Pipfile`
- `Pipfile.lock`
- `requirements.txt`
- `config.local.sample.mk`
- `configs/`
- `lib/`
- `lemmafreq/`
- `models/`
- `cookbook/`
- `cookbook-repo-addons/`

Useful targeted review commands:

```bash
git log <previous-tag>..HEAD --oneline -- lib/
git log <previous-tag>..HEAD --oneline -- lemmafreq/
git log <previous-tag>..HEAD --oneline -- cookbook-repo-addons/
git log <previous-tag>..HEAD --oneline -- cookbook/
git diff <previous-tag>..HEAD -- cookbook/paths_lingproc.mk configs/
git diff <previous-tag>..HEAD -- Pipfile Pipfile.lock requirements.txt
```

### 2. Review Linguistic Processing Changes

For changes to `lib/spacy_linguistic_processing.py`, confirm whether the release
changes any output contract or processing semantics:

- supported languages or spaCy models,
- POS tag mapping, especially Luxembourgish `LB_TAG_MAP`,
- title processing and `tsents`,
- sentence or token field names,
- lemma behavior,
- NER output behavior,
- document filtering thresholds,
- JSON schema validation behavior,
- `model_id`, `lid_path`, `lingproc_git`, or other metadata.

If any of these change, document the impact in release notes and decide whether
`RUN_VERSION_LINGPROC` must change.

### 3. Review Make and S3 Orchestration Changes

Review changes to path, sync, processing, and upload behavior:

- S3 bucket defaults such as `S3_BUCKET_REBUILT`, `S3_BUCKET_LINGPROC`, and
  `S3_BUCKET_LINGPROC_COMPONENT`,
- `RUN_ID_LINGPROC` construction,
- `LINGPROC_LANGIDENT_NEEDED`,
- WIP marker behavior and max age settings,
- `local_to_s3` upload options,
- `NEWSPAPER`, provider, and collection-list handling,
- `COLLECTION_JOBS`, `NEWSPAPER_JOBS`, and `MAX_LOAD`.

Do not change S3 path conventions or stamp-file semantics without calling that
out explicitly as a breaking operational change.

### 4. Review Lemma-Frequency Changes

For changes under `lemmafreq/`, `lib/s3_lemmafreq.py`, or
`cookbook-repo-addons/lemmafreq.mk`, confirm:

- default `LEMMAFREQ_POS_TAGS`,
- default `LEMMAFREQ_MIN_LENGTH`,
- output filename label behavior,
- newspaper/language recomputation granularity,
- wrapped JSON metadata fields,
- merge behavior for language-level `ALL` files,
- Rust binary rebuild/test status.

If lemma-frequency output semantics change, update `README-LEMMAFREQ.md` and the
release notes.

### 5. Review Dependency and Model State

Check:

- `Pipfile`
- `Pipfile.lock`
- `requirements.txt`
- `cookbook/lib/pyproject.toml`
- `lemmafreq/Cargo.toml`
- `lemmafreq/Cargo.lock`
- `models/lb_model/model-best/`

Questions to answer before release:

- Are spaCy model versions intentional and documented?
- Did dependency changes come from an intentional lock refresh?
- Is Python 3.11 still the intended runtime?
- Did Rust dependencies or the Rust compiler baseline change?
- Did bundled Luxembourgish model metadata or licensing notes change?

### 6. Update Documentation

Review and update documentation when the release changes behavior, supported
languages, targets, dependencies, or operational workflow.

Common files to review:

- `README.md`
- `README-LEMMAFREQ.md`
- `AGENT.md`
- `config.local.sample.mk`
- `env.sample`
- `cookbook/README.md` if shared cookbook behavior changed
- `cookbook/AGENT.md` if shared cookbook agent guidance changed

This repository currently keeps historical release notes in `README.md` rather
than a root-level `CHANGELOG.md`. For a release, either update the README
release notes section or add a root changelog deliberately and use it
consistently going forward. In either case, keep release entries in newest-first
order, with the newest release at the top.

### 7. Perform Release Verification

Use lightweight checks first:

```bash
python3 -m py_compile lib/spacy_linguistic_processing.py lib/s3_lemmafreq.py
cargo test --manifest-path lemmafreq/Cargo.toml
make help
```

On macOS, run Make commands through `remake` or `gmake`, while keeping examples
written as `make` in documentation.

If dependency setup changed, also check the project environment:

```bash
pipenv run python --version
pipenv run python -m py_compile lib/spacy_linguistic_processing.py lib/s3_lemmafreq.py
```

If spaCy setup or model requirements changed:

```bash
make check-spacy-pipelines
```

If you have valid S3 credentials and intentionally want runtime verification,
run a small known-good target. This is optional and environment-dependent:

```bash
make all NEWSPAPER=<provider>/<newspaper> NEWSPAPER_JOBS=1 MAX_LOAD=1
```

For lemma frequency changes, a local fixture-driven compute or Rust test is
preferred over a full S3 run unless the release specifically changes S3
orchestration.

### 8. Prepare the Pull Request

Before releasing, ensure the release-ready branch is reviewed and merged into
`main`.

Recommended checks before opening the PR:

- the branch contains release notes and README/changelog updates,
- the working tree is clean,
- the branch is pushed to GitHub,
- the branch diff against `main` matches the intended release scope.

Useful commands:

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
git push origin <release-branch>
```

Then open the PR:

```bash
gh pr create --base main --head <release-branch>
```

Or open it through the GitHub web interface.

After approval, resolve and merge the PR manually in GitHub. Do not use
automatic PR merge commands from the CLI for the normal release flow.

### 9. Sync Local `main` Before Tagging

Do not create the release tag from the feature branch. After the PR is merged:

```bash
git checkout main
git pull --ff-only origin main
git log -1 --oneline
```

Verify that the top commit on `main` is the merged release commit that contains:

- `README.md` release notes or root `CHANGELOG.md`,
- `RELEASE_NOTES_<tag>.md`,
- all intended pipeline, configuration, dependency, and documentation changes.

## Release Notes

Release notes should be created before tagging and committed together with the
final release-ready state. Historical release-note or changelog sections should
be maintained in newest-first order.

### Filename

Use the exact git tag string in the filename:

```text
RELEASE_NOTES_<tag>.md
```

Examples:

- `RELEASE_NOTES_v2026.05.01.md`
- `RELEASE_NOTES_v2026.06.15.md`

### Suggested Structure

Release notes for this repository should focus on processing impact,
reproducibility, S3 output paths, and operational changes.

Suggested sections:

1. Overview
2. Linguistic processing changes
3. Lemma-frequency changes
4. Make/S3 orchestration changes
5. Dependency and model changes
6. Output compatibility and migration notes
7. Validation performed
8. Known limitations or follow-up work

Template:

```markdown
# Release Notes - <tag>

**Release Date:** YYYY-MM-DD
**Tag:** <tag>
**Status:** Stable

## Overview

Brief summary of the release.

## Linguistic Processing

- Changes to spaCy processing, supported languages, schemas, or output fields.
- Whether `RUN_VERSION_LINGPROC` changed.
- Resulting `RUN_ID_LINGPROC`, if relevant.

## Lemma Frequencies

- Changes to `LEMMAFREQ_POS_TAGS`, `LEMMAFREQ_MIN_LENGTH`, output format, or aggregation.

## Orchestration

- Changes to Make targets, S3 paths, WIP behavior, stamps, or parallelism.

## Dependencies and Models

- Python, spaCy, model, Rust, or cookbook dependency changes.

## Compatibility and Migration

- Any rerun, recomputation, S3 cleanup, or downstream migration required.

## Validation

- Checks performed before release.

## Known Issues

- Known limitations, if any.

## Links

- Repository: https://github.com/impresso/impresso-linguistic-processing
```

### Generating Change Lists

Use git to build the release notes content:

```bash
git log <previous-tag>..HEAD --oneline
git shortlog <previous-tag>..HEAD -sn
git diff <previous-tag>..HEAD --stat
git diff <previous-tag>..HEAD --name-status
git diff <previous-tag>..HEAD -- lib/ lemmafreq/ cookbook-repo-addons/
git diff <previous-tag>..HEAD -- Makefile README.md README-LEMMAFREQ.md AGENT.md
git diff <previous-tag>..HEAD -- Pipfile Pipfile.lock requirements.txt
```

## Publishing a Release

### 1. Commit Release Notes and Final Metadata

Before tagging, commit the release notes and any final release-ready updates:

```bash
git add README.md README-LEMMAFREQ.md AGENT.md RELEASE_PROCESS.md RELEASE_NOTES_<tag>.md
git commit -m "Prepare release <tag>"
```

Adjust the staged file list to match the actual release contents. Depending on
the release, you may also include:

- `Makefile`
- `Pipfile`
- `Pipfile.lock`
- `requirements.txt`
- `config.local.sample.mk`
- `configs/*`
- `lib/*`
- `lemmafreq/*`
- `cookbook/*`
- `cookbook-repo-addons/*`
- `models/*`

### 2. Open and Merge the Pull Request

Push the release branch and merge it into `main` before creating the tag.

The pull request should be resolved manually in GitHub.

Example:

```bash
git push origin <release-branch>
gh pr create --base main --head <release-branch>
```

Then review and merge the PR manually in the GitHub web UI, and afterwards sync
local `main`:

```bash
git checkout main
git pull --ff-only origin main
```

### 3. Create the Git Tag

Create an annotated tag from the exact merged release commit on `main`:

```bash
git tag -a <tag> -m "Release <tag>"
git push origin <tag>
```

Example:

```bash
git tag -a v2026.05.01 -m "Release v2026.05.01"
git push origin v2026.05.01
```

Before tagging, confirm you are on `main` and on the merged release commit:

```bash
git branch --show-current
git log -1 --oneline
```

### 4. Create the GitHub Release

#### Via GitHub Web Interface

1. Go to https://github.com/impresso/impresso-linguistic-processing/releases
2. Click "Draft a new release"
3. Select the tag you just pushed
4. Use the tag string as the title, or add a short descriptive suffix
5. Paste the contents of the committed `RELEASE_NOTES_<tag>.md` file into the description
6. Publish the release

#### Via GitHub CLI

```bash
gh auth login

gh release create <tag> \
   --title "<tag>" \
   --notes-file RELEASE_NOTES_<tag>.md
```

Example:

```bash
gh release create v2026.05.01 \
   --title "v2026.05.01" \
   --notes-file RELEASE_NOTES_v2026.05.01.md
```

Using `--notes-file` is preferred because the published GitHub release text then
matches the committed release notes in git.

### 5. Correcting an Existing Release

If you must fix a published release description after the fact:

```bash
gh release edit <tag> --notes-file RELEASE_NOTES_<tag>.md
```

Treat this as an exception path. The normal flow is to finalize the release
notes before tagging.

## Post-Release Tasks

### 1. Verify the Published Release

After publishing:

- confirm the tag exists on GitHub,
- confirm the GitHub release points to the correct commit,
- confirm the tagged commit is reachable from `main`,
- confirm the release notes match the committed file,
- confirm the README release entry or changelog entry is present in the tagged
  snapshot.

### 2. Verify Clone and Setup Instructions

Ensure the documented setup flow still makes sense for the new release:

```bash
git clone --recursive https://github.com/impresso/impresso-linguistic-processing.git
cd impresso-linguistic-processing
python3.11 -mpip install pipenv
python3.11 -mpipenv install
python3.11 -mpipenv shell
make help
```

On macOS, use `remake help` or `gmake help`.

If the release changed environment assumptions, update:

- `README.md`
- `README-LEMMAFREQ.md`
- `config.local.sample.mk`
- `env.sample`

### 3. Notify Stakeholders

Depending on the release, notify relevant team members about:

- new `RUN_ID_LINGPROC` values,
- changed supported languages or model versions,
- output format or schema changes,
- required reruns or recomputation,
- lemma-frequency output changes,
- S3 bucket/path changes,
- dependency or environment changes.

### 4. Monitor for Follow-up Issues

After release:

- watch GitHub issues,
- track failures in S3 processing runs,
- inspect logs for WIP lock or upload failures,
- be prepared to issue a follow-up tag if a run ID, dependency, model, or S3 path
  was wrong.

### 5. If a Release Was Created from the Wrong Branch

If a release was published from a feature branch before the PR was merged:

1. delete the GitHub release,
2. delete the incorrect tag locally and on origin if appropriate,
3. merge the branch through a PR into `main`,
4. recreate the tag from `main`,
5. republish the GitHub release.

Example cleanup commands:

```bash
git tag -d <tag>
git push origin :refs/tags/<tag>
```

Only do this if you are intentionally replacing the release and have confirmed
the team agrees with rewriting that published tag.

## Hotfix Releases

Use a hotfix release when a published tag contains an incorrect configuration,
broken target wiring, or other release-critical issue.

Typical cases:

- wrong `RUN_VERSION_LINGPROC` or `RUN_ID_LINGPROC`,
- wrong S3 bucket or prefix,
- broken Make target,
- broken spaCy model dependency,
- incorrect `Pipfile.lock` or `Cargo.lock`,
- incorrect lemma-frequency output naming or merge behavior,
- missing documentation for required reruns or output migration.

Suggested process:

```bash
git checkout -b hotfix/<tag-fix> <released-tag>
# make the fix
git commit -am "Fix release issue for <new-tag>"
git tag -a <new-tag> -m "Hotfix release <new-tag>"
git push origin <new-tag>
```

Then create a focused GitHub release with notes describing exactly what was
corrected.

## Checklist

- [ ] Reviewed commits and file changes since the previous tag
- [ ] Reviewed linguistic processing changes and output compatibility
- [ ] Reviewed Make/S3 orchestration, WIP, and stamp behavior
- [ ] Reviewed lemma-frequency changes
- [ ] Reviewed `Pipfile`, `Pipfile.lock`, `requirements.txt`, and Rust dependencies
- [ ] Reviewed bundled model assets and spaCy model versions
- [ ] Updated `README.md` release notes or root changelog
- [ ] Updated `README-LEMMAFREQ.md`, `AGENT.md`, or config samples if needed
- [ ] Decided whether `RUN_VERSION_LINGPROC` must change
- [ ] Verified Python syntax
- [ ] Verified Rust tests for lemma-frequency changes
- [ ] Verified `make help` with GNU Make, `remake`, or `gmake`
- [ ] Verified spaCy pipelines if model/dependency setup changed
- [ ] Wrote `RELEASE_NOTES_<tag>.md` before tagging
- [ ] Committed release notes on the release branch
- [ ] Opened PR and resolved it manually in GitHub
- [ ] Merged PR into `main`
- [ ] Synced local `main` to the merged release commit
- [ ] Created and pushed annotated git tag from `main`
- [ ] Published GitHub release from the committed release notes file
- [ ] Performed post-release verification

## Tools and Resources

- GitHub repository: https://github.com/impresso/impresso-linguistic-processing
- GitHub releases: https://github.com/impresso/impresso-linguistic-processing/releases
- GitHub issues: https://github.com/impresso/impresso-linguistic-processing/issues
- GitHub CLI: https://cli.github.com/
- Keep a Changelog: https://keepachangelog.com/
- Git tagging documentation: https://git-scm.com/book/en/v2/Git-Basics-Tagging

## Questions?

If you have questions about the release process:

- review recent tags and release notes,
- check previous GitHub releases for examples,
- inspect `README.md` release notes for historical pipeline changes,
- ask maintainers before publishing a tag that changes `RUN_ID_LINGPROC`,
  output formats, or S3 path conventions.

---

**Last Updated:** 2026-05-01
