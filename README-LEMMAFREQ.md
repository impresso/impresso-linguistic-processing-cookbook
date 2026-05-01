# Lemma Frequency Distribution System

## Overview

This document describes the lemma frequency distribution creation pipeline in the Impresso linguistic processing cookbook. The system computes lemma frequency statistics from linguistically processed newspaper text, organized by newspaper and language, for use in downstream applications such as topic modeling.

**Purpose**: Create document-level and corpus-level lemma frequency distributions for Named Entities (PROPN) and Common Nouns (NOUN) from historical newspaper collections.

**Target Use Cases**:

- Topic modeling with vocabulary filtering and weighting
- Document similarity computation
- Named entity prominence analysis
- Temporal trend analysis of entity mentions

## Architecture

The lemma frequency pipeline consists of three main components:

1. **Rust Counter** (`lemmafreq/aggregate_lemma_frequencies.rs`): High-performance streaming aggregator
2. **Python Orchestrator** (`lib/s3_lemmafreq.py`): S3 I/O, subprocess management, metadata wrapping
3. **Make Targets** (`cookbook-repo-addons/lemmafreq.mk`): Build orchestration and parallelization

### Data Flow

```
S3 linguistic-processing JSONL.bz2 (year-level, by newspaper)
  ↓
  → Rust binary (streaming aggregation with filtering)
  ↓
Lemma frequencies JSON.bz2 (newspaper-level, by language)
  ↓
  → Python merge operation
  ↓
Corpus-level lemma frequencies JSON.bz2 (by language)
```

## Input Data Format

The system processes linguistic processing JSONL files with the following structure:

```json
{
  "ci_id": "AATA-1846-02-21-a-i0001",
  "sents": [
    {
      "lg": "en",
      "tokens": [
        { "t": "House", "p": "NOUN", "l": "house", "o": 0 },
        { "t": "Bern", "p": "PROPN", "l": "Bern", "o": 6 }
      ]
    }
  ],
  "tsents": [
    {
      "lg": "en",
      "tokens": [{ "t": "Zürich", "p": "PROPN", "o": 20 }]
    }
  ]
}
```

**Input Field Conventions**:

- `sents`: Regular sentences from OCR text
- `tsents`: Title sentences (page/article titles)
- `lg`: Language code (ISO 639-1: de, fr, en, lb)
- `tokens` or `tok`: Token array (both field names supported)
- `t`: Surface token text
- `p`: Universal POS tag (UPOS)
- `l`: Lemma (lowercase canonical form)
- `o`: Character offset (not used by lemma frequency)

**Fallback Logic**:

- If `l` (lemma) is missing, uses `t` (surface text) as lemma
- Processes both `sents` and `tsents` arrays
- Accepts both `tokens` and `tok` field names

## Output Data Format

### Newspaper-Level Output

**File Pattern**: `{NEWSPAPER}.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2`

**Example**: `BL-AATA.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2`

```json
{
  "newspaper": "BL-AATA",
  "language": "en",
  "pos_tags": ["PROPN", "NOUN"],
  "min_length": 2,
  "run_id": "lingproc-spacy_v3.6.0-multilingual_v1-0-3",
  "freqs": {
    "house": 342,
    "bern": 128,
    "london": 2847,
    "parliament": 567,
    "zürich": 94
  }
}
```

### Corpus-Level Output (Aggregated)

**File Pattern**: `ALL.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2`

```json
{
  "language": "de",
  "pos_tags": ["PROPN", "NOUN"],
  "min_length": 2,
  "run_id": "lingproc-spacy_v3.6.0-multilingual_v1-0-3",
  "source_count": 347,
  "freqs": {
    "deutschland": 145832,
    "regierung": 98234,
    "zürich": 45621,
    "bundesrat": 23456
  }
}
```

**Metadata Fields**:

- `newspaper`: Newspaper identifier (newspaper-level only)
- `language`: ISO 639-1 language code
- `pos_tags`: Array of UPOS tags included
- `min_length`: Minimum lemma length filter (in characters)
- `run_id`: Linguistic processing pipeline version/run identifier
- `source_count`: Number of newspaper files merged (corpus-level only)
- `freqs`: Lemma → frequency mapping (all lemmas lowercase)

## Configuration Parameters

### User-Configurable Variables (Makefile)

```makefile
# POS tags to include (comma-separated)
LEMMAFREQ_POS_TAGS ?= PROPN,NOUN

# Minimum lemma length in characters
LEMMAFREQ_MIN_LENGTH ?= 2

# Logging level
LEMMAFREQ_LOGGING_LEVEL ?= INFO

# WIP marker expiration (hours)
LEMMAFREQ_WIP_MAX_AGE ?= 2
```

**Default Selection**:

- **POS Tags**: `PROPN,NOUN` (Named Entities and Common Nouns)
  - Rationale: These capture key topics, entities, and themes
  - Alternative options: Add `VERB`, `ADJ` for broader coverage
- **Min Length**: `2` characters
  - Rationale: Filters single-letter lemmas and abbreviations
  - Consider increasing to 3-4 for cleaner topic modeling vocabulary

### Path Structure

**S3 Output Base Path**:

```
s3://{S3_BUCKET_LINGPROC_COMPONENT}/lemma-freq/{RUN_ID_LINGPROC}/{LANGUAGE}/{NEWSPAPER}.{SELECTION_LABEL}.lemmafreq.json.bz2
```

**Example**:

```
s3://impresso-lingproc-components/lemma-freq/lingproc-spacy_v3.6.0-multilingual_v1-0-3/de/BNF-legaulois.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2
```

## Build Targets

### Compute Newspaper-Level Frequencies

```bash
# Single newspaper, single language
make compute-lemma-frequencies-BL/AATA-en

# All newspapers for one language
make compute-lemma-frequencies-de
make compute-lemma-frequencies-fr
make compute-lemma-frequencies-en
make compute-lemma-frequencies-lb

# All newspapers, all languages
make compute-all-lemma-frequencies
```

### Aggregate to Corpus Level

```bash
# Single language
make aggregate-lemma-frequencies-de

# All languages
make aggregate-lemma-frequencies
```

## Processing Logic

### Rust Counter Algorithm

1. **Stream JSONL lines** from stdin
2. **Parse JSON** for each document
3. **Extract tokens** from `sents` and `tsents` arrays
4. **Filter by**:
   - Language code matches target language
   - POS tag in allowed set (e.g., PROPN, NOUN)
   - Lemma length ≥ minimum threshold
5. **Normalize**: Convert lemma to lowercase
6. **Accumulate**: Increment frequency counter
7. **Output**: JSON object with lemma → count mapping

### Python Orchestration

The `s3_lemmafreq.py` script provides two commands:

#### Compute Command

```bash
python lib/s3_lemmafreq.py compute \
  --s3-prefix s3://bucket/lingproc-output/NEWSPAPER \
  --binary lemmafreq/target/release/aggregate_lemma_frequencies \
  --language de \
  --pos-tags PROPN,NOUN \
  --min-length 2 \
  --run-id lingproc-v1-0-3 \
  --newspaper NEWSPAPER \
  -o output.lemmafreq.json.bz2 \
  --log-file process.log.gz
```

**Behavior**:

- Lists all `*.jsonl.bz2` files under S3 prefix
- Streams content through Rust binary
- Wraps result with metadata
- Writes compressed JSON output

#### Merge Command

```bash
python lib/s3_lemmafreq.py merge \
  --s3-prefix s3://bucket/lemma-freq/RUN_ID/de \
  --suffix .lemmafreq.json.bz2 \
  --language de \
  --pos-tags PROPN,NOUN \
  --min-length 2 \
  --run-id lingproc-v1-0-3 \
  -o ALL.lemmafreq.json.bz2 \
  --log-file merge.log.gz
```

**Behavior**:

- Lists all matching lemmafreq files under prefix
- Skips files starting with `ALL_` or `ALL.`
- Sums frequency counts across newspapers
- Outputs corpus-level aggregate

## Using Lemma Frequencies for Topic Modeling

### Vocabulary Filtering

Lemma frequencies enable intelligent vocabulary filtering for topic models:

```python
import json
from smart_open import open as smart_open

# Load corpus-level lemma frequencies
with smart_open('s3://bucket/lemma-freq/.../de/ALL.upos-PROPN_NOUN.minlength-2.lemmafreq.json.bz2', 'r') as f:
    data = json.load(f)
    freqs = data['freqs']

# Filter by document frequency thresholds
MIN_DF = 10   # Remove rare lemmas (< 10 occurrences)
MAX_DF = 50000  # Remove common lemmas (> 50k occurrences)

filtered_vocab = {
    lemma: count
    for lemma, count in freqs.items()
    if MIN_DF <= count <= MAX_DF
}

# Use as topic model vocabulary
vocabulary = list(filtered_vocab.keys())
```

### TF-IDF Weighting

Use corpus frequencies as IDF (inverse document frequency) weights:

```python
import numpy as np

# Total number of documents in corpus
N = data.get('source_count', len(freqs))

# Compute IDF for each lemma
# IDF(t) = log(N / df(t)) where df(t) is document frequency
idf_weights = {
    lemma: np.log(N / count)
    for lemma, count in freqs.items()
}
```

### Extracting Document Lemmas

Example workflow for extracting lemmas from linguistic processing documents:

```python
from collections import Counter
import json

def extract_document_lemmas(doc_jsonl_path, language='de', pos_tags={'PROPN', 'NOUN'}, min_length=2):
    """Extract lemmas from a single document matching criteria."""
    lemmas = []

    with smart_open(doc_jsonl_path, 'r') as f:
        for line in f:
            doc = json.loads(line)

            # Process both sents and tsents
            for sent in doc.get('sents', []) + doc.get('tsents', []):
                if sent.get('lg') != language:
                    continue

                for token in sent.get('tokens', sent.get('tok', [])):
                    if token.get('p') not in pos_tags:
                        continue

                    lemma = token.get('l', token.get('t', '')).lower()
                    if len(lemma) >= min_length:
                        lemmas.append(lemma)

    return lemmas
```

**Usage with Topic Modeling Tools**:

The extracted lemmas can be used with any topic modeling framework (Mallet, Gensim, scikit-learn, etc.). Most tools expect either:

- A list of lemmas per document (for bag-of-words models)
- A vocabulary list derived from corpus-level frequencies (for vocabulary filtering)
- Document-term frequency matrices

### Temporal Topic Analysis

Lemma frequencies can support temporal analysis:

```python
# Load lemma frequencies by year
year_freqs = {}
for year in range(1800, 1900):
    path = f's3://.../lemma-freq/{year}/ALL.lemmafreq.json.bz2'
    with smart_open(path, 'r') as f:
        year_freqs[year] = json.load(f)['freqs']

# Track lemma prominence over time
def track_lemma(lemma, year_freqs):
    return {
        year: freqs.get(lemma, 0)
        for year, freqs in year_freqs.items()
    }

# Example: Track "parliament" mentions over time
parliament_trend = track_lemma('parliament', year_freqs)
```

## Performance Characteristics

### Processing Speed

- **Rust counter**: ~100-200 MB/s on standard hardware
- **Typical newspaper** (100k documents): 2-5 minutes
- **Full corpus** (347 newspapers): Parallelizable via Make

### Resource Usage

- **Memory**: Rust binary uses ~50-200 MB (proportional to vocabulary size)
- **Disk**: Compressed output is 10-100 KB per newspaper
- **S3 Transfer**: Streaming reduces local disk usage

## Troubleshooting

### Common Issues

**Missing Rust Toolchain**:

```bash
# Ubuntu/Debian
sudo apt install -y rustc cargo

# macOS
brew install rust
```

**WIP Lock Conflicts**:

- WIP markers prevent concurrent processing of the same file
- Automatically expire after `LEMMAFREQ_WIP_MAX_AGE` hours (default: 2)
- Manually remove: `aws s3 rm s3://.../NEWSPAPER.wip`

**Empty Frequency Output**:

- Check language code matches input documents
- Verify POS tags exist in source data
- Ensure lemma field `l` is populated (or fallback to `t`)

**Memory Issues**:

- Reduce parallelization: `make -j1` instead of `make -j8`
- Process newspapers individually instead of bulk targets

## Future Enhancements

### Potential Extensions

1. **Document-Level Frequencies**: Output per-document lemma distributions (not just aggregates)
2. **Additional POS Tags**: Include VERB, ADJ for broader semantic coverage
3. **Bigram/Trigram Support**: Extend to multi-word expressions
4. **Temporal Granularity**: Year/decade-level aggregates for trend analysis
5. **TF-IDF Output**: Pre-compute weighted frequencies
6. **Stopword Integration**: Apply domain-specific stopword lists during aggregation

## Related Components

- **Linguistic Processing Pipeline**: Produces the input JSONL files
  - Path: `s3://{S3_BUCKET_LINGPROC_CANONICAL}/`
  - Run ID: Defined by `RUN_ID_LINGPROC` variable
- **S3 Aggregator**: Generic tool for S3 JSONL processing
  - Script: `cookbook/lib/s3_aggregator.py`
  - Use for extracting lemmas without frequency computation

- **Local-to-S3 Sync**: Uploads outputs with metadata
  - Module: `impresso_cookbook.local_to_s3`
  - Handles WIP markers and timestamp preservation

## References

- Universal Dependencies POS Tags: https://universaldependencies.org/u/pos/
- spaCy Lemmatization: https://spacy.io/usage/linguistic-features#lemmatization
