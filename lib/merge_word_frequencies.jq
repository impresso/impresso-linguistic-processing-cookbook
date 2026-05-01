# Merge multiple word frequency JSON objects into a single frequency distribution
# Input: array of frequency distribution JSON objects
# Output: single merged frequency distribution JSON object

# Helper function to merge two frequency objects
def merge_frequencies(a; b):
  (a // {}) as $freq_a |
  (b // {}) as $freq_b |
  ([$freq_a | keys[], $freq_b | keys[]] | unique) as $all_keys |
  reduce $all_keys[] as $key ({}; 
    .[$key] = (($freq_a[$key] // 0) + ($freq_b[$key] // 0))
  );

# Main processing: merge all frequency distributions
[inputs] |
map(select(type == "object" and length > 0)) |
reduce .[] as $freq ({}; 
  merge_frequencies(.; $freq)
)
