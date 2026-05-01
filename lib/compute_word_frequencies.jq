# Extract tokens for the specified language and compute frequency distribution
# Expects LANGUAGE environment variable to be set (e.g., "de", "fr", "en")
# Input: linguistic processing JSON objects (streamed)
# Output: JSON object with content ID and word frequencies

def get_language: env.LANGUAGE // "de";

# Stream all documents, including the first one; ignore null when run with -n
def docs: (., inputs) | select(. != null);

# Streaming frequency computation - process one document at a time
reduce docs as $doc ({}; 
  . + {
      id: ($doc.id // $doc.ci_id // $doc.cid //"unknown"),
      freqs: (reduce ($doc
              | (.sents // [])[]
              | select(.lg == get_language)
              | ((.tokens // .tok) // [])[]
              | .t) as $token ({}; 
        .[$token] = ((.[$token] // 0) + 1)
      ))
    }
)
