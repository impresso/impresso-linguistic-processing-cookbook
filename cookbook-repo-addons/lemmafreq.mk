#### ENABLE LOGGING FIRST

default: help

# Configuration
PYTHON ?= python3
CARGO ?= cargo
AWS ?= aws

PROVIDER_LIST ?= BCUL BL BNF BNL FedGaz LeTemps NZZ SNL SWA SWISSINFO

LEMMAFREQ_PREFIXES ?= $(addprefix s3://142-processed-data-final/,$(PROVIDER_LIST))

LEMMAFREQ_OUTPUT_DIR ?= $(BUILD_DIR)/142-component-final/lemma-frequencies
LEMMAFREQ_BIN ?= lemmafreq/target/release/aggregate_lemma_frequencies
LEMMAFREQ_LOG_LEVEL ?= $(LOGGING_LEVEL)
LEMMAFREQ_S3_PREFIX ?=

# Environment variables for Rust binary
LEMMAFREQ_LANGUAGE ?= de
LEMMAFREQ_POS_TAGS ?= PROPN,NOUN
LEMMAFREQ_MIN_LENGTH ?= 2

ifneq ($(strip $(LEMMAFREQ_S3_PREFIX)),)
LEMMAFREQ_S3_PREFIX := $(LEMMAFREQ_S3_PREFIX:%/=%)/
endif

$(call log.info, LEMMAFREQ_PREFIXES)
$(call log.info, LEMMAFREQ_OUTPUT_DIR)
$(call log.info, LEMMAFREQ_S3_PREFIX)
$(call log.info, LEMMAFREQ_LANGUAGE)
$(call log.info, LEMMAFREQ_POS_TAGS)
$(call log.info, LEMMAFREQ_MIN_LENGTH)

# Path helpers
extract_basename = $(strip $(notdir $(patsubst %/,%,$(1))))
data_path = $(LEMMAFREQ_OUTPUT_DIR)/$(call extract_basename,$(1)).jsonl.zst
json_path = $(LEMMAFREQ_OUTPUT_DIR)/$(call extract_basename,$(1)).lemmafreq.json
s3_uri = $(LEMMAFREQ_S3_PREFIX)$(call extract_basename,$(1)).lemmafreq.json

# Normalize prefix by adding trailing slash if not present
normalize_prefix = $(if $(filter %/,$(1)),$(1),$(1)/)

lemmafreq-setup: $(LEMMAFREQ_BIN)
# Build lemmafreq binary
$(LEMMAFREQ_BIN):
	$(MAKE_SILENCE_RECIPE)$(CARGO) build --release --manifest-path lemmafreq/Cargo.toml

# Download linguistic processing data from S3
define download_rule
$(call data_path,$(1)):
	$(MAKE_SILENCE_RECIPE)mkdir -p $$(@D)
	$(MAKE_SILENCE_RECIPE)$(AWS) s3 cp $(call normalize_prefix,$(1)) $$@ --recursive --exclude "*" --include "*.jsonl.zst" || { rm -f $$@; exit 1; }
endef

# Generate lemma frequency JSON as PROVIDER.lemmafreq.json
define lemmafreq_rule
$(call json_path,$(1)): $(LEMMAFREQ_BIN)
	$(MAKE_SILENCE_RECIPE)mkdir -p $$(@D)
	$(MAKE_SILENCE_RECIPE)$(AWS) s3 cp $(call normalize_prefix,$(1)) - --recursive --exclude "*" --include "*.jsonl.zst" | \
		zstdcat | \
		LANGUAGE=$(LEMMAFREQ_LANGUAGE) \
		POS_TAGS=$(LEMMAFREQ_POS_TAGS) \
		MIN_LENGTH=$(LEMMAFREQ_MIN_LENGTH) \
		$(LEMMAFREQ_BIN) > $$@.tmp && mv $$@.tmp $$@
endef

# Upload lemma frequencies to S3
define upload_rule
$(call json_path,$(1)).uploaded: $(call json_path,$(1))
	$(MAKE_SILENCE_RECIPE)$(AWS) s3 cp $$< $(call s3_uri,$(1)) && touch $$@
endef

$(foreach p,$(LEMMAFREQ_PREFIXES),$(eval $(call lemmafreq_rule,$(p))))
$(foreach p,$(LEMMAFREQ_PREFIXES),$(eval $(call upload_rule,$(p))))

JSON_TARGETS := $(foreach p,$(LEMMAFREQ_PREFIXES),$(call json_path,$(p)))
UPLOAD_TARGETS := $(foreach p,$(LEMMAFREQ_PREFIXES),$(call json_path,$(p)).uploaded)


# Targets
.PHONY: lemmafreq lemmafreq-upload clean-lemmafreq

lemmafreq: $(JSON_TARGETS)
	@echo "Lemma frequencies: $(LEMMAFREQ_OUTPUT_DIR)/*.lemmafreq.json"

lemmafreq-upload: $(UPLOAD_TARGETS)
	@echo "Uploaded to: $(LEMMAFREQ_S3_PREFIX)"

clean-lemmafreq:
	$(MAKE_SILENCE_RECIPE)rm -rf $(LEMMAFREQ_OUTPUT_DIR)

help::
	@echo "  lemmafreq LEMMAFREQ_PREFIXES=\"s3://...\"              # Generate lemma frequencies (PROVIDER.lemmafreq.json)"
	@echo "  lemmafreq-upload LEMMAFREQ_S3_PREFIX=\"s3://...\"     # Upload lemma frequencies to S3"
	@echo "  lemmafreq LEMMAFREQ_LANGUAGE=de POS_TAGS=PROPN,NOUN  # Configure filtering options"
	@echo "  clean-lemmafreq                                      # Remove all outputs"
