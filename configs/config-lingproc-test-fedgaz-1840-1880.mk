# Test configuration: lingproc with chunking on FedGaz (DE and FR), 1840-1880
#
# Uses the lingproc length defaults: LINGPROC_MIN_DOC_LENGTH=50,
# LINGPROC_MAX_DOC_LENGTH=500000, LINGPROC_CHUNK_SIZE=50000.
# Processing runs on this machine. The lingproc recipe always uploads its
# results, so outputs go to the sandbox bucket under a separate test run
# version and never touch the production run in 142-processed-data-final.
# FedGaz rebuilt data starts in 1849; earlier years in the range have no input.
#
# Usage:
#   make refresh-newspaper-list CFG=configs/config-lingproc-test-fedgaz-1840-1880.mk
#   make collection CFG=configs/config-lingproc-test-fedgaz-1840-1880.mk
# Single newspaper:
#   make newspaper CFG=configs/config-lingproc-test-fedgaz-1840-1880.mk NEWSPAPER=FedGaz/FedGazDe

USE_CANONICAL := 1
NEWSPAPER_HAS_PROVIDER := 1
SHELL := /bin/bash
LOGGING_LEVEL := INFO
MAKE_SILENCE_RECIPE := $(EMPTY)

# Input: rebuilt data, language taken from the rebuilt files
S3_BUCKET_REBUILT := 122-rebuilt-final
LINGPROC_LANGIDENT_NEEDED := 0

# Output: sandbox bucket and test run version
S3_BUCKET_LINGPROC := 140-processed-data-sandbox
RUN_VERSION_LINGPROC := v1-0-4-test-chunking

# Selection: FedGazDe and FedGazFr, one collection entry per year.
# make refresh-newspaper-list discovers the matching PROVIDER/NEWSPAPER/YEAR
# entries in the rebuilt bucket (only years that exist) and writes them to
# NEWSPAPERS_TO_PROCESS_FILE. NEWSPAPER and NEWSPAPER_YEARS apply to
# single-newspaper runs (make newspaper).
S3_PREFIX_NEWSPAPERS_TO_PROCESS_BUCKET := $(S3_BUCKET_REBUILT)
NEWSPAPER_FNMATCH := FedGaz/*
NEWSPAPER_LIST_INCLUDE_YEARS := 1
NEWSPAPER_LIST_YEARS := $(shell seq 1849 1880)
NEWSPAPER := FedGaz/FedGazDe
NEWSPAPER_YEARS := $(NEWSPAPER_LIST_YEARS)
NEWSPAPERS_TO_PROCESS_FILE := configs/newspapers-test-fedgaz-1849-1880.txt
NEWSPAPER_YEAR_SORTING := cat

# Length thresholds and chunking (the defaults, set explicitly for the test)
LINGPROC_MIN_DOC_LENGTH := 50
LINGPROC_MAX_DOC_LENGTH := 500000
LINGPROC_CHUNK_SIZE := 50000

# Local test run: keep output files locally, no WIP markers on S3
LINGPROC_WIP_ENABLED :=
PROCESSING_QUIT_IF_S3_OUTPUT_EXISTS_OPTION := --quit-if-s3-output-exists
