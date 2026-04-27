#### ENABLE LOGGING FIRST

# Repo-specific lemma frequency tooling.
#
# The cookbook owns generic S3/local orchestration helpers. This add-on owns the
# lemma statistics product and calls the Rust counter through lib/s3_lemmafreq.py.

PYTHON ?= python3
CARGO ?= cargo
RUSTC ?= rustc

# USER-VARIABLE: LEMMAFREQ_BIN
# Rust binary used for high-performance lemma frequency counting.
LEMMAFREQ_BIN ?= lemmafreq/target/release/aggregate_lemma_frequencies
  $(call log.debug, LEMMAFREQ_BIN)


# VARIABLE: LEMMAFREQ_RUST_SOURCES
# Rust sources and Cargo metadata that should trigger a binary rebuild.
LEMMAFREQ_RUST_SOURCES := lemmafreq/Cargo.toml $(wildcard lemmafreq/Cargo.lock) $(wildcard lemmafreq/*.rs)
  $(call log.debug, LEMMAFREQ_RUST_SOURCES)


# USER-VARIABLE: LEMMAFREQ_POS_TAGS
# POS tags included in lemma frequency aggregation.
LEMMAFREQ_POS_TAGS ?= PROPN,NOUN
  $(call log.debug, LEMMAFREQ_POS_TAGS)


# USER-VARIABLE: LEMMAFREQ_MIN_LENGTH
# Minimum lemma length included in lemma frequency aggregation.
LEMMAFREQ_MIN_LENGTH ?= 2
  $(call log.debug, LEMMAFREQ_MIN_LENGTH)


# USER-VARIABLE: LEMMAFREQ_LOGGING_LEVEL
# Logging level for the Python S3/Rust driver.
LEMMAFREQ_LOGGING_LEVEL ?= $(LOGGING_LEVEL)
  $(call log.debug, LEMMAFREQ_LOGGING_LEVEL)


# USER-VARIABLE: LEMMAFREQ_WIP_MAX_AGE
# Maximum age in hours for stale lemma frequency WIP markers.
LEMMAFREQ_WIP_MAX_AGE ?= 2
  $(call log.debug, LEMMAFREQ_WIP_MAX_AGE)


# VARIABLE: S3_LEMMA_FREQS_BASE_PATH
# Base S3 path for lemma frequency files in the component bucket.
S3_LEMMA_FREQS_BASE_PATH := s3://$(S3_BUCKET_LINGPROC_COMPONENT)/lemma-freq/$(RUN_ID_LINGPROC)
  $(call log.debug, S3_LEMMA_FREQS_BASE_PATH)


# VARIABLE: LOCAL_LEMMA_FREQS_BASE_PATH
# Local path for lemma frequency files before upload.
LOCAL_LEMMA_FREQS_BASE_PATH := $(BUILD_DIR)/$(S3_BUCKET_LINGPROC_COMPONENT)/lemma-freq/$(RUN_ID_LINGPROC)
  $(call log.debug, LOCAL_LEMMA_FREQS_BASE_PATH)


lemmafreq_json_path = $(LOCAL_LEMMA_FREQS_BASE_PATH)/$(2)/$(1).lemmafreq.json.bz2
lemmafreq_log_path = $(LOCAL_LEMMA_FREQS_BASE_PATH)/$(2)/$(1).lemmafreq.log.gz
lemmafreq_s3_json_path = $(S3_LEMMA_FREQS_BASE_PATH)/$(2)/$(1).lemmafreq.json.bz2
lemmafreq_s3_log_path = $(S3_LEMMA_FREQS_BASE_PATH)/$(2)/$(1).lemmafreq.log.gz


setup:: check-rust-toolchain


# TARGET: check-rust-toolchain
#: Verify that the Rust compiler and Cargo are available for lemma frequency computation
check-rust-toolchain:
	@missing=0; \
	if ! command -v $(RUSTC) >/dev/null 2>&1; then \
		echo "Rust compiler not found: $(RUSTC)"; \
		missing=1; \
	fi; \
	if ! command -v $(CARGO) >/dev/null 2>&1; then \
		echo "Cargo not found: $(CARGO)"; \
		missing=1; \
	fi; \
	if [ $$missing -ne 0 ]; then \
		echo ""; \
		echo "Install the Rust toolchain before running lemma frequency targets."; \
		echo ""; \
		echo "Ubuntu/Debian:"; \
		echo "  sudo apt update"; \
		echo "  sudo apt install -y rustc cargo"; \
		echo ""; \
		echo "macOS/Homebrew:"; \
		echo "  brew update"; \
		echo "  brew install rust"; \
		echo ""; \
		exit 1; \
	fi


$(LEMMAFREQ_BIN): check-rust-toolchain $(LEMMAFREQ_RUST_SOURCES)
	$(MAKE_SILENCE_RECIPE)$(CARGO) build --release --manifest-path lemmafreq/Cargo.toml


setup-lemmafreq: $(LEMMAFREQ_BIN)


lemmafreq-setup: setup-lemmafreq


# PATTERN-RULE: compute-lemma-frequencies-%-de
#: Compute German lemma frequency distribution for a specific newspaper
compute-lemma-frequencies-%-de: $(LEMMAFREQ_BIN)
	@mkdir -p $(LOCAL_LEMMA_FREQS_BASE_PATH)/de
	@set +e; \
	$(PYTHON) -m impresso_cookbook.local_to_s3 --exit-2-if-exists --s3-file-exists $(S3_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 --wip --wip-max-age $(LEMMAFREQ_WIP_MAX_AGE) --create-wip $(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 $(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.log.gz ; status=$$?; \
	set -e; \
	if [ $$status -eq 2 ]; then \
		echo "File already exists or WIP in progress, skipping processing for $*.lemmafreq.json.bz2"; \
	elif [ $$status -ne 0 ]; then \
		exit $$status; \
	else \
		$(PYTHON) lib/s3_lemmafreq.py compute \
		--s3-prefix s3://$(PATH_LINGPROC_BASE)/$* \
		--binary $(LEMMAFREQ_BIN) \
		--language de \
		--pos-tags $(LEMMAFREQ_POS_TAGS) \
		--min-length $(LEMMAFREQ_MIN_LENGTH) \
		--run-id $(RUN_ID_LINGPROC) \
		--newspaper $* \
		-o $(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 \
		--log-file $(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.log.gz \
		--log-level $(LEMMAFREQ_LOGGING_LEVEL) && \
		$(PYTHON) -m impresso_cookbook.local_to_s3 \
		--keep-timestamp-only \
		--set-timestamp \
		--ts-key __file__ \
		--remove-wip \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.json.bz2 \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/de/$*.lemmafreq.log.gz; \
	fi


# PATTERN-RULE: compute-lemma-frequencies-%-fr
#: Compute French lemma frequency distribution for a specific newspaper
compute-lemma-frequencies-%-fr: $(LEMMAFREQ_BIN)
	@mkdir -p $(LOCAL_LEMMA_FREQS_BASE_PATH)/fr
	@set +e; \
	$(PYTHON) -m impresso_cookbook.local_to_s3 --exit-2-if-exists --s3-file-exists $(S3_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 --wip --wip-max-age $(LEMMAFREQ_WIP_MAX_AGE) --create-wip $(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 $(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.log.gz ; status=$$?; \
	set -e; \
	if [ $$status -eq 2 ]; then \
		echo "File already exists or WIP in progress, skipping processing for $*.lemmafreq.json.bz2"; \
	elif [ $$status -ne 0 ]; then \
		exit $$status; \
	else \
		$(PYTHON) lib/s3_lemmafreq.py compute \
		--s3-prefix s3://$(PATH_LINGPROC_BASE)/$* \
		--binary $(LEMMAFREQ_BIN) \
		--language fr \
		--pos-tags $(LEMMAFREQ_POS_TAGS) \
		--min-length $(LEMMAFREQ_MIN_LENGTH) \
		--run-id $(RUN_ID_LINGPROC) \
		--newspaper $* \
		-o $(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 \
		--log-file $(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.log.gz \
		--log-level $(LEMMAFREQ_LOGGING_LEVEL) && \
		$(PYTHON) -m impresso_cookbook.local_to_s3 \
		--keep-timestamp-only \
		--set-timestamp \
		--ts-key __file__ \
		--remove-wip \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.json.bz2 \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/fr/$*.lemmafreq.log.gz; \
	fi


# PATTERN-RULE: compute-lemma-frequencies-%-en
#: Compute English lemma frequency distribution for a specific newspaper
compute-lemma-frequencies-%-en: $(LEMMAFREQ_BIN)
	@mkdir -p $(LOCAL_LEMMA_FREQS_BASE_PATH)/en
	@set +e; \
	$(PYTHON) -m impresso_cookbook.local_to_s3 --exit-2-if-exists --s3-file-exists $(S3_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 --wip --wip-max-age $(LEMMAFREQ_WIP_MAX_AGE) --create-wip $(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 $(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.log.gz ; status=$$?; \
	set -e; \
	if [ $$status -eq 2 ]; then \
		echo "File already exists or WIP in progress, skipping processing for $*.lemmafreq.json.bz2"; \
	elif [ $$status -ne 0 ]; then \
		exit $$status; \
	else \
		$(PYTHON) lib/s3_lemmafreq.py compute \
		--s3-prefix s3://$(PATH_LINGPROC_BASE)/$* \
		--binary $(LEMMAFREQ_BIN) \
		--language en \
		--pos-tags $(LEMMAFREQ_POS_TAGS) \
		--min-length $(LEMMAFREQ_MIN_LENGTH) \
		--run-id $(RUN_ID_LINGPROC) \
		--newspaper $* \
		-o $(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 \
		--log-file $(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.log.gz \
		--log-level $(LEMMAFREQ_LOGGING_LEVEL) && \
		$(PYTHON) -m impresso_cookbook.local_to_s3 \
		--keep-timestamp-only \
		--set-timestamp \
		--ts-key __file__ \
		--remove-wip \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.json.bz2 \
		$(LOCAL_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/en/$*.lemmafreq.log.gz; \
	fi


# Explicitly generate per-newspaper targets so newspaper ids containing provider
# prefixes, such as BNF/legaulois, are matched as full target names.
define compute_lemma_frequency_rule
compute-lemma-frequencies-$(1)-$(2): $(LEMMAFREQ_BIN)
	@mkdir -p $(dir $(call lemmafreq_json_path,$(1),$(2)))
	@set +e; \
	$(PYTHON) -m impresso_cookbook.local_to_s3 --exit-2-if-exists --s3-file-exists $(call lemmafreq_s3_json_path,$(1),$(2)) --wip --wip-max-age $(LEMMAFREQ_WIP_MAX_AGE) --create-wip $(call lemmafreq_json_path,$(1),$(2)) $(call lemmafreq_s3_json_path,$(1),$(2)) $(call lemmafreq_log_path,$(1),$(2)) $(call lemmafreq_s3_log_path,$(1),$(2)) ; status=$$$$?; \
	set -e; \
	if [ $$$$status -eq 2 ]; then \
		echo "File already exists or WIP in progress, skipping processing for $(1).lemmafreq.json.bz2"; \
	elif [ $$$$status -ne 0 ]; then \
		exit $$$$status; \
	else \
		$(PYTHON) lib/s3_lemmafreq.py compute \
		--s3-prefix s3://$(PATH_LINGPROC_BASE)/$(1) \
		--binary $(LEMMAFREQ_BIN) \
		--language $(2) \
		--pos-tags $(LEMMAFREQ_POS_TAGS) \
		--min-length $(LEMMAFREQ_MIN_LENGTH) \
		--run-id $(RUN_ID_LINGPROC) \
		--newspaper $(1) \
		-o $(call lemmafreq_json_path,$(1),$(2)) \
		--log-file $(call lemmafreq_log_path,$(1),$(2)) \
		--log-level $(LEMMAFREQ_LOGGING_LEVEL) && \
		$(PYTHON) -m impresso_cookbook.local_to_s3 \
		--keep-timestamp-only \
		--set-timestamp \
		--ts-key __file__ \
		--remove-wip \
		$(call lemmafreq_json_path,$(1),$(2)) $(call lemmafreq_s3_json_path,$(1),$(2)) \
		$(call lemmafreq_log_path,$(1),$(2)) $(call lemmafreq_s3_log_path,$(1),$(2)); \
	fi
endef

$(foreach newspaper,$(ALL_NEWSPAPERS),$(foreach language,de fr en,$(eval $(call compute_lemma_frequency_rule,$(newspaper),$(language)))))


# PATTERN-RULE: aggregate-lemma-frequencies-%
#: Combine newspaper lemma frequency distributions for a language
aggregate-lemma-frequencies-%:
	@mkdir -p $(LOCAL_LEMMA_FREQS_BASE_PATH)/$*
	$(PYTHON) lib/s3_lemmafreq.py merge \
	--s3-prefix $(S3_LEMMA_FREQS_BASE_PATH)/$* \
	--suffix .lemmafreq.json.bz2 \
	--language $* \
	--pos-tags $(LEMMAFREQ_POS_TAGS) \
	--min-length $(LEMMAFREQ_MIN_LENGTH) \
	--run-id $(RUN_ID_LINGPROC) \
	-o $(LOCAL_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.json.bz2 \
	--log-file $(LOCAL_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.log.gz \
	--log-level $(LEMMAFREQ_LOGGING_LEVEL)
	$(PYTHON) -m impresso_cookbook.local_to_s3 \
	--keep-timestamp-only \
	--set-timestamp \
	--ts-key __file__ \
	$(LOCAL_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.json.bz2 $(S3_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.json.bz2 \
	$(LOCAL_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.log.gz $(S3_LEMMA_FREQS_BASE_PATH)/$*/ALL.lemmafreq.log.gz


# TARGET: compute-lemma-frequencies-de
#: Compute German lemma frequencies for all newspapers
compute-lemma-frequencies-de: $(foreach newspaper,$(ALL_NEWSPAPERS),compute-lemma-frequencies-$(newspaper)-de)


# TARGET: compute-lemma-frequencies-fr
#: Compute French lemma frequencies for all newspapers
compute-lemma-frequencies-fr: $(foreach newspaper,$(ALL_NEWSPAPERS),compute-lemma-frequencies-$(newspaper)-fr)


# TARGET: compute-lemma-frequencies-en
#: Compute English lemma frequencies for all newspapers
compute-lemma-frequencies-en: $(foreach newspaper,$(ALL_NEWSPAPERS),compute-lemma-frequencies-$(newspaper)-en)


# TARGET: compute-all-lemma-frequencies
#: Compute lemma frequencies for all supported languages
compute-all-lemma-frequencies: compute-lemma-frequencies-de compute-lemma-frequencies-fr compute-lemma-frequencies-en


# TARGET: compute-lemma-frequencies
#: Compute German lemma frequencies by default
compute-lemma-frequencies: compute-lemma-frequencies-de


help::
	@echo "  setup-lemmafreq                    # Build the Rust lemma frequency binary"
	@echo "  check-rust-toolchain               # Check Rust compiler and Cargo availability"
	@echo "  compute-lemma-frequencies-de       # Compute German lemma frequencies"
	@echo "  compute-lemma-frequencies-fr       # Compute French lemma frequencies"
	@echo "  compute-lemma-frequencies-en       # Compute English lemma frequencies"
	@echo "  compute-all-lemma-frequencies      # Compute lemma frequencies for all supported languages"
	@echo "  aggregate-lemma-frequencies-de     # Merge German newspaper lemma frequencies"


.PHONY: setup-lemmafreq lemmafreq-setup check-rust-toolchain
.PHONY: compute-lemma-frequencies-de compute-lemma-frequencies-fr compute-lemma-frequencies-en
.PHONY: compute-all-lemma-frequencies compute-lemma-frequencies
