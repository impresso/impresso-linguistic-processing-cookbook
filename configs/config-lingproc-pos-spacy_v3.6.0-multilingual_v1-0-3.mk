# Production lingproc run: spaCy 3.6.0 multilingual, run version v1-0-3
#
# Usage:
#   make collection CFG=configs/config-lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3.mk
#   make newspaper CFG=configs/config-lingproc-pos-spacy_v3.6.0-multilingual_v1-0-3.mk NEWSPAPER=FedGaz/FedGazDe

USE_CANONICAL := 1
NEWSPAPER_HAS_PROVIDER := 1
SHELL := /bin/bash
LOGGING_LEVEL := INFO
MAKE_SILENCE_RECIPE := $(EMPTY)

# Input: rebuilt data; the language is taken from the rebuilt files
S3_BUCKET_REBUILT := 122-rebuilt-final
LINGPROC_LANGIDENT_NEEDED := 0

# Output
S3_BUCKET_LINGPROC := 142-processed-data-final
RUN_VERSION_LINGPROC := v1-0-3

# Newspaper selection: discovered from the rebuilt bucket, years in random order
S3_PREFIX_NEWSPAPERS_TO_PROCESS_BUCKET := $(S3_BUCKET_REBUILT)
NEWSPAPER_YEAR_SORTING := shuf
# NEWSPAPER_FNMATCH := BNF/*
# NEWSPAPER := BL/WTCH

# Skip outputs that already exist on S3; S3 WIP locking against concurrent workers
PROCESSING_QUIT_IF_S3_OUTPUT_EXISTS_OPTION := --quit-if-s3-output-exists
LINGPROC_WIP_ENABLED := 1
# Treat locks older than this many hours as stale
LINGPROC_WIP_MAX_AGE := 1

# Further settings and their cookbook defaults (uncomment to override)

# # Disable JSON schema validation of the output
# LINGPROC_VALIDATE_OPTION :=

# # Build directory for local stamps, logs and transient outputs
# BUILD_DIR := build.d

# # File with the newspapers (or PROVIDER/NEWSPAPER/YEAR items) to process
# NEWSPAPERS_TO_PROCESS_FILE := $(BUILD_DIR)/newspapers.txt

# # Parallelism: newspapers in parallel, jobs per newspaper, load limit
# # (defaults are derived from the number of CPUs)
# COLLECTION_JOBS := 4
# NEWSPAPER_JOBS := 2
# MAX_LOAD := 8

# # Language identification input, only used with LINGPROC_LANGIDENT_NEEDED := 1
# S3_BUCKET_LANGIDENT := 140-processed-data-sandbox
# PROCESS_LABEL_LANGIDENT := langident
# TASK_LANGIDENT := lid
# MODEL_ID_LANGIDENT := ensemble_multilingual
# RUN_VERSION_LANGIDENT := v2-0-2

# # Output run identifier parts; RUN_VERSION_LINGPROC is set above
# PROCESS_LABEL_LINGPROC := lingproc
# TASK_LINGPROC := pos
# MODEL_ID_LINGPROC := spacy_v3.6.0-multilingual

# # Document length thresholds and chunking (characters, title plus full text)
# LINGPROC_MIN_DOC_LENGTH := 50
# LINGPROC_MAX_DOC_LENGTH := 500000
# LINGPROC_CHUNK_SIZE := 50000

# # Reprocess and upload even if S3 output exists, or upload only if newer
# LINGPROC_FORCE_OVERWRITE_OPTION := --force-overwrite
# LINGPROC_UPLOAD_IF_NEWER_OPTION := --upload-if-newer
