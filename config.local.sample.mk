# adapt any variable here

# Sample configuration for local build settings

# Set the logging level: DEBUG, INFO, WARNING, ERROR
LOGGING_LEVEL ?= INFO

# The build directory where all local input and output files are stored
BUILD_DIR ?= build.d

# Specify the newspaper to process. Just a suffix appended to the s3 bucket name
NEWSPAPER ?= actionfem

# A file containing a space-separated line with all newspapers to process
NEWSPAPERS_TO_PROCESS_FILE ?= $(BUILD_DIR)/newspapers.txt

# Order the years of a newspaper to process by recency (default is random order)
NEWSPAPER_YEAR_SORTING ?= shuf
# For the default order, comment the line above and uncomment the line below
# NEWSPAPER_YEAR_SORTING ?= cat

# The input bucket for rebuilt data
S3_BUCKET_REBUILT ?= 122-rebuilt-final

# The run version for input data
RUN_VERSION_LANGINDENT ?= v1-4-4

# The output bucket for processed data
S3_BUCKET_LINGPROC ?= 140-processed-data-sandbox

# The task for output data
TASK_LINGPROC ?= pos

# The model ID for output data
MODEL_ID_LINGPROC ?= spacy_v3.6.0-multilingual

# The run version for output data
RUN_VERSION_LINGPROC ?= v2-0-0

# Prevent any output to S3 even if s3-output-path is set
LINGPROC_S3_OUTPUT_DRY_RUN ?=

# Keep only the local timestamp output files after uploading
LINGPROC_KEEP_TIMESTAMP_ONLY_OPTION ?= --keep-timestamp-only

# Quit the processing if the output file already exists in S3
LINGPROC_QUIT_IF_S3_OUTPUT_EXISTS_OPTION ?= --quit-if-s3-output-exists

# Set the number of parallel launches of newspapers (uses xargs)
PARALLEL_NEWSPAPERS ?= 1

# Set the number of parallel jobs of newspaper-year files to process
MAKE_PARALLEL_PROCESSING_NEWSPAPER_YEAR ?= 1

# The local path for rebuilt data
LOCAL_PATH_REBUILT ?= $(BUILD_DIR)/$(S3_BUCKET_REBUILT)/$(NEWSPAPER)

# The local path for language identification data
LOCAL_PATH_LANGIDENT ?= $(BUILD_DIR)/$(IN_S3_BUCKET_PROCESSED_DATA)/$(PROCESS_LABEL_LANGINDENT)/$(RUN_VERSION_LANGINDENT)/$(NEWSPAPER)

# The local path for linguistic processing output
LOCAL_PATH_LINGPROC ?= $(BUILD_DIR)/$(S3_BUCKET_LINGPROC)/$(PROCESS_LABEL_LINGPROC)$(PROCESS_SUBTYPE_LABEL_LINGPROC)/$(RUN_ID_LINGPROC)/$(NEWSPAPER)

# The S3 path for linguistic processing output
S3_PATH_LINGPROC ?= s3://$(S3_BUCKET_LINGPROC)/$(PROCESS_LABEL_LINGPROC)$(PROCESS_SUBTYPE_LABEL_LINGPROC)/$(RUN_ID_LINGPROC)/$(NEWSPAPER)
