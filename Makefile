# Makefile for linguistic processing for newspapers
# Read the README.md for more information on how to use this Makefile.
# Or run `make` for online help.

# Load our make logging functions
include cookbook/log.mk

# USER-VARIABLE: CONFIG_LOCAL_MAKE
# Defines the name of the local configuration file to include.
#
# This file is used to override default settings and provide local configuration. If a
# file with this name exists in the current directory, it will be included. If the file
# does not exist, it will be silently ignored. Never add the file called config.local.mk
# to the repository! If you have stored config files in the repository set the
# CONFIG_LOCAL_MAKE variable to a different name.
CONFIG_LOCAL_MAKE ?= config.local.mk
ifdef CFG
  CONFIG_LOCAL_MAKE := $(CFG)
  $(info Overriding CONFIG_LOCAL_MAKE to $(CONFIG_LOCAL_MAKE) from CFG variable)
else
  $(call log.info, CONFIG_LOCAL_MAKE)
endif
# Load local config if it exists (ignore silently if it does not exists)
-include $(CONFIG_LOCAL_MAKE)


# Now we can use the logging function to show the current logging level
  $(call log.info, LOGGING_LEVEL)



# Help: Show this help message
help::
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  setup                 # Prepare the local directories"
	@echo "  collection            # Call make all for each newspaper found in the file $(NEWSPAPERS_TO_PROCESS_FILE)"
	@echo "  all                   # Resync the data from the S3 bucket to the local directory and process all years of a single newspaper"
	@echo "  newspaper             # Process a single newspaper for all years"
	@echo "  sync                  # Sync the data from the S3 bucket to the local directory"
	@echo "  resync                # Remove the local synchronization file stamp and sync again."
	@echo "  clean-build           # Remove the entire build directory"
	@echo "  clean-newspaper       # Remove the local directory for a single newspaper"
	@echo "  update-requirements   # Update the requirements.txt file with the current pipenv requirements."
	@echo "  lb-spacy-package      # Package the Luxembourgish spaCy model"
	@echo "  help                  # Show this help message"



###
# INCLUDES AND CONFIGURATION FILES
#------------------------------------------------------------------------------

# Set shared make options
include cookbook/make_settings.mk

# Load general setup
include cookbook/setup.mk

# Load setup rules for linguistic processing
include cookbook/setup_lingproc.mk

# Load newspaper list configuration and processing rules
include cookbook/newspaper_list.mk

# Load input path definitions for rebuilt content
include cookbook/paths_rebuilt.mk

# Load input path definitions for language identification
include cookbook/paths_langident.mk

# Load output path definitions for linguistic processing
include cookbook/paths_lingproc.mk 



###
# MAIN TARGETS
#------------------------------------------------------------------------------

include cookbook/main_targets.mk

###
# SYNCHRONIZATION TARGETS
#------------------------------------------------------------------------------

include cookbook/sync.mk

# Include synchronization rules for rebuilt content
include cookbook/sync_rebuilt.mk

# Include synchronization rules for langident content
include cookbook/sync_langident.mk

# Include synchronization rules for linguistic processing output
include cookbook/sync_lingproc.mk

# Include cleanup rules
include cookbook/clean.mk


###
# PROCESSING TARGETS
#------------------------------------------------------------------------------
# General processing options
include cookbook/processing.mk

# Include main linguistic processing rules
include cookbook/processing_lingproc.mk

# Include aggregation rules for linguistic processing
include cookbook/aggregators_lingproc.mk

###
# FINAL DECLARATIONS AND UTILITIES
#------------------------------------------------------------------------------


# Include path conversion utilities
include cookbook/local_to_s3.mk

# Include testing and inspection utilities
include cookbook-repo-addons/test_eyeball_lingproc.mk

# lemmafreq tooling
include cookbook-repo-addons/lemmafreq.mk
