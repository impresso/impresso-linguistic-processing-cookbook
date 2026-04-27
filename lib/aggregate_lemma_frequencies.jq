# Aggregate lemmas across all documents into a single frequency distribution
# Filters tokens by POS tag and minimum lemma length
# Input: linguistic processing JSON objects (streamed)
# Output: Single JSON object with lemma frequencies across all documents
# Environment variables:
#   LANGUAGE: language code to filter (default: "de")
#   POS_TAGS: comma or space-separated POS tags (default: "PROPN,NOUN")
#   MIN_LENGTH: minimum lemma length in characters (default: "2")

# Stream all documents, including the first one; ignore null when run with -n
def docs: (., inputs) | select(. != null);

# Compute parameters once outside the loop for efficiency
(env.LANGUAGE // "de") as $language |
((env.POS_TAGS // "PROPN,NOUN") | gsub(" "; ",") | split(",") | map(select(length > 0))) as $pos_tags |
((env.MIN_LENGTH // "2") | tonumber) as $min_length |

# Aggregate frequency computation - process all documents into single dictionary
reduce docs as $doc ({}; 
  reduce ($doc
    | ((.sents // []) + (.tsents // []))[]
    | select(.lg == $language)
    | ((.tokens // .tok) // [])[]
    | select(.p as $pos | $pos_tags | index($pos))
    | (.l // .t) # | ascii_downcase
    | select(length >= $min_length)
  ) as $lemma (.; 
    .[$lemma] = ((.[$lemma] // 0) + 1)
  )
)
