# Information on impresso linguistic preprocessing

This repository implements the following linguistic processing steps:

- POS tagging
- NER tagging
- improved lemmatization

We do this for the following languages:

- fr
- de
- lb (only POS tagging)
- en

The Luxembourgish language model is taken from
https://github.com/PeterGilles/Luxembourgish-language-resources/tree/master/lux-tagger-July2023/model-best
und unknown licencing status. We set the version and name in the model's meta data to lux-tagger-July2023.

## Prerequisites

The build process has been tested on modern Linux and macOS systems and requires
Python 3.11. Under Ubuntu/Debian, make sure to have the following packages installed:

```sh
# install linux tools and python3.11 according on Debian/Ubuntu
sudo bash cookbook/install_apt.sh

# on macos with brew
sudo bash cookbook/install_brew.sh
```

This repository uses `pipenv`.

```sh
git clone --recursive https://github.com/impresso/impresso-linguistic-processing.git
cd impresso-linguistic-processing
python3.11 -mpip install pipenv
python3.11 -mpipenv install
python3.11 -mpipenv shell
```

For s3-based file processing, the following environment variables need to be set:

```sh
SE_ACCESS_KEY=
SE_SECRET_KEY=
SE_HOST_URL=
```

If your global environment does not contain these variables, you can set them in a local
`.env` file. The `python-dotenv` package is used to read these variables.

```sh
cp env.sample .env
edit .env
```

# Running the pipeline

## Local configuration

Adapt the local paths for the input and output directories in the
`config.local.mk` (see `config.local.mk.sample` for default settings.)

```sh
cp config.local.mk.sample config.local.mk
edit config.local.mk
```

## Available Make targets

The build process is controlled by the `Makefile`. Main targets include:

```sh
make help                    # show available targets
make setup                   # initialize development environment
make newspaper               # process specific newspaper/year pairs in parallel
make collection              # process all newspapers
make clean                   # clean build artifacts
make clean-build             # remove all generated files
```

### Lemma Frequency Targets

Lemma frequency computation is implemented as newspaper/language build targets.
For example, `compute-lemma-frequencies-BL/AATA-en` reads all matching
year-level linguistic-processing files below:

```text
s3://<processed-bucket>/lingproc/<run-id>/BL/AATA/
```

and writes one newspaper-level output:

```text
s3://<component-bucket>/lemma-freq/<run-id>/en/BL/AATA.lemmafreq.json.bz2
```

The build does not track individual S3 newspaper-year files as Make
prerequisites. If a single year file is regenerated or replaced on S3, the
smallest supported recomputation unit is the whole newspaper for that language.
Delete the corresponding newspaper-level lemma frequency output and its `.wip`
marker, then rerun the language target.

The language-level aggregation targets, such as `aggregate-lemma-frequencies-en`,
merge the newspaper-level outputs into `ALL.lemmafreq.json.bz2`.

## Processing options

For newspaper processing, several options are available:

```sh
# Process with specific parallelism
make newspaper MAKE_PARALLEL_OPTION=16

# Process specific newspapers
make newspaper NEWSPAPERS="GDL IMP"

# Process specific years
make newspaper YEARS="1900 1901"

# Combine options
make newspaper NEWSPAPERS="GDL" YEARS="1900" MAKE_PARALLEL_OPTION=8
```

## Command-Line Options for `spacy_linguistic_processing.py`

The `lib/spacy_linguistic_processing.py` script supports several command-line options:

- `--lid`: Path to the language identification file.
- `--language`: Specify a language code to use for all items.
- `-o`, `--output-path`: Path to the output file (default: `out.jsonl`).
- `--min-doc-length`: Minimum document length to process (default: 50).
- `--validate`: Validate the final language identification JSON against the schema.
- `--text-property`: Specify the JSON property that contains the full text (default: `ft`).
- `--git-version`: Set the git version to include in the output. If not set, the `GIT_VERSION` environment variable is used.
- `--quit-if-s3-output-exists`: Quit if the output file already exists in the specified S3 bucket.
- `--s3-output-path`: S3 path to upload the output file after processing or check if it already exists.
- `--keep-timestamp-only`: After uploading to S3, keep only the timestamp of the local output file for data efficiency.

## Build System Structure

The build system is organized into several make include files:

- `config.local.mk`: Local configuration overrides (not in the repository)

# Uploading to impresso S3 bucket

Ensure that the environment variables `SE_ACCESS_KEY` and `SE_SECRET_KEY` for access to the
S3 impresso infrastructure are set, e.g., by setting them in a local `.env` file.

The build process uploads the processed data to the impresso S3 bucket.

# Processing Workflow Overview

This overview explains the impresso linguistic preprocessing pipeline, focusing on efficient data processing, distributed scalability, and minimizing interference between machines.

## Key Features

### Data Storage on S3

All input and output data reside on S3, allowing multiple machines to access shared data without conflicts. Processing directly from S3 reduces the need for local storage.

### Local Stamp Files

Local **stamp files** mirror S3 metadata, enabling machines to independently track and manage processing tasks without downloading full datasets. This prevents interference between machines, as builds are verified against S3 before processing starts, ensuring no overwrites or duplicate results.

### Makefile and Build Dependencies

The Makefile orchestrates the pipeline by defining independent targets and dependencies based on stamp files. Each machine maintains its local state, ensuring stateless and conflict-free builds.

### Running Local Commands

Processing scripts operate independently, handling data in a randomized order. Inputs are read from S3, outputs are uploaded back to S3, and no synchronization is required between machines. Additional machines can join or leave without disrupting ongoing tasks.

### Uploading Results to S3

Processed files are validated locally and uploaded to S3 with integrity checks (e.g., JSON schema validation and md5sum). Results are never overwritten, ensuring consistency even with concurrent processing.

### Handling Large Datasets on Small Machines

By leveraging S3 and stamp files, machines with limited storage (e.g., 100GB) can process large datasets efficiently without downloading entire files.

### Parallelization

- **Local Parallelization**: Each machine uses Make's parallel build feature to maximize CPU utilization.
- **Distributed Parallelization**: Machines process separate subsets of data independently (e.g., by newspaper or date range) and write results to S3 without coordination.

### Multi-Machine Build Isolation

- **Stateless Processing**: Scripts rely only on S3 and local configurations, avoiding shared state.
- **Custom Configurations**: Each machine uses local configuration files or environment variables to tailor processing behavior.

## Summary

The impresso pipeline ensures scalable, distributed processing by:

- Using **S3 for centralized storage** and avoiding shared local state.
- Leveraging **local stamp files** for machine-specific tracking.
- Defining **independent Makefile targets** for parallel builds.
- Employing **stateless scripts** that operate independently.
- Ensuring **concurrent data handling** through S3’s consistency features.

This architecture supports efficient, isolated builds, enabling multiple machines to process large datasets seamlessly and reliably.

# Release notes:

- 2024-12-28: v2-0-0

  - feat/fix: Process titles of content items (even if they sometimes are prefixes of the
    full text) and store them in new tsents field.
  - feat: use updated v2 json schema with ci_id as content item id
  - feat: add sampling of processed content items for testing
  - refactor: refactor monolithic Makefile into smaller reusable cookbook parts

- 2024-11-30: v1-0-4

  - note: no change to spaCy pipelines and output content
  - fix: upload to s3 was not compressed. This has been fixed.
  - feat: separate s3 compression script to carefully compress uncompressed files on s3
  - chore: small improvements

- 2024-11-27: v1-0-3

  - chore: improve logging and add length limit for input text

- 2024-11-25: v1-0-1

  - fix: POS tagging of lb was buggy (all tags set to X). This has been fixed.
  - feat: Generate log files for each newspaper/year pair and upload it to s3.
  - feat: Support agreed nameing convention for output files.
  - feat: Process directly from s3 input data, on-the-fly mirroring per newspaper for
    slim builds
  - note: no change to spaCy pipelines apart from lb POS tag mapping

- 2024-04-24: v1-0-0

  - First public release of the impresso linguistic processing pipeline.

  ## About Impresso

### Impresso project

[Impresso - Media Monitoring of the Past](https://impresso-project.ch) is an interdisciplinary research project that aims to develop and consolidate tools for processing and exploring large collections of media archives across modalities, time, languages and national borders. The first project (2017-2021) was funded by the Swiss National Science Foundation under grant No. [CRSII5_173719](http://p3.snf.ch/project-173719) and the second project (2023-2027) by the SNSF under grant No. [CRSII5_213585](https://data.snf.ch/grants/grant/213585) and the Luxembourg National Research Fund under grant No. 17498891.

### Copyright

Copyright (C) 2024 The Impresso team.

### License

This program is provided as open source under the [GNU Affero General Public License](https://github.com/impresso/impresso-pyindexation/blob/master/LICENSE) v3 or later.

---

<p align="center">
  <img src="https://github.com/impresso/impresso.github.io/blob/master/assets/images/3x1--Yellow-Impresso-Black-on-White--transparent.png?raw=true" width="350" alt="Impresso Project Logo"/>
</p>
