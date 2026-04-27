use serde_json::Value;
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{self, BufRead, BufReader};
use std::time::Instant;

/// Size of the buffer for reading
const BUFFER_SIZE: usize = 64 * 1024;

fn collect_lemma_frequencies<R: BufRead>(
    input: R,
    language: &str,
    pos_tags: &[String],
    min_length: usize,
) -> io::Result<(HashMap<String, u64>, u64, u64)> {
    let mut freq: HashMap<String, u64> = HashMap::new();
    let mut total_docs = 0u64;
    let mut total_tokens = 0u64;

    for (line_num, line_result) in input.lines().enumerate() {
        let line = line_result?;

        // Parse JSON
        let doc: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("Warning: JSON parse error at line {}: {}", line_num + 1, e);
                continue;
            }
        };

        total_docs += 1;

        // Process both sents and tsents arrays
        let mut all_sents = Vec::new();
        if let Some(sents) = doc.get("sents").and_then(|v| v.as_array()) {
            all_sents.extend(sents.iter());
        }
        if let Some(tsents) = doc.get("tsents").and_then(|v| v.as_array()) {
            all_sents.extend(tsents.iter());
        }

        // Process each sentence
        for sent in all_sents {
            // Check language
            if let Some(lg) = sent.get("lg").and_then(|v| v.as_str()) {
                if lg != language {
                    continue;
                }
            } else {
                continue;
            }

            // Get tokens array (try "tok" first, then "tokens")
            let tokens = sent
                .get("tok")
                .or_else(|| sent.get("tokens"))
                .and_then(|v| v.as_array());

            if let Some(tokens) = tokens {
                for token in tokens {
                    // Check POS tag
                    if let Some(pos) = token.get("p").and_then(|v| v.as_str()) {
                        if !pos_tags.iter().any(|tag| tag == pos) {
                            continue;
                        }
                    } else {
                        continue;
                    }

                    // Get lemma (try "l" first, then fall back to "t")
                    let lemma = token
                        .get("l")
                        .or_else(|| token.get("t"))
                        .and_then(|v| v.as_str());

                    if let Some(lemma) = lemma {
                        let lemma_lower = lemma.to_lowercase();
                        if lemma_lower.len() >= min_length {
                            *freq.entry(lemma_lower).or_insert(0) += 1;
                            total_tokens += 1;
                        }
                    }
                }
            }
        }
    }

    Ok((freq, total_docs, total_tokens))
}

fn main() -> io::Result<()> {
    // Parse environment variables for filtering
    let language = env::var("LANGUAGE").unwrap_or_else(|_| "de".to_string());
    let pos_tags: Vec<String> = env::var("POS_TAGS")
        .unwrap_or_else(|_| "PROPN,NOUN".to_string())
        .split(|c| c == ',' || c == ' ')
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .collect();
    let min_length: usize = env::var("MIN_LENGTH")
        .unwrap_or_else(|_| "2".to_string())
        .parse()
        .unwrap_or(2);

    eprintln!(
        "Config: LANGUAGE={}, POS_TAGS={:?}, MIN_LENGTH={}",
        language, pos_tags, min_length
    );

    // Parse command-line arguments: read from file if specified, otherwise stdin
    let args: Vec<String> = env::args().collect();
    let input: Box<dyn BufRead> = if args.len() > 1 {
        Box::new(BufReader::with_capacity(BUFFER_SIZE, File::open(&args[1])?))
    } else {
        Box::new(BufReader::with_capacity(BUFFER_SIZE, io::stdin()))
    };

    let start_time = Instant::now();
    let (freq, total_docs, total_tokens) =
        collect_lemma_frequencies(input, &language, &pos_tags, min_length)?;

    // Print final statistics
    eprintln!(
        "\r... processed {:>8} docs, {:>12} tokens, {:>8} unique lemmas in {:>6.2}s",
        total_docs,
        total_tokens,
        freq.len(),
        start_time.elapsed().as_secs_f64()
    );

    // Output as JSON
    serde_json::to_writer(io::stdout(), &freq).expect("failed to write JSON");
    println!(); // Add newline after JSON

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn collect(
        input: &str,
        language: &str,
        pos_tags: &[&str],
        min_length: usize,
    ) -> HashMap<String, u64> {
        let tags = pos_tags
            .iter()
            .map(|tag| tag.to_string())
            .collect::<Vec<_>>();
        collect_lemma_frequencies(Cursor::new(input), language, &tags, min_length)
            .expect("fixture should be readable")
            .0
    }

    #[test]
    fn counts_lemmas_from_sents_and_tsents() {
        let input = r#"{"sents":[{"lg":"de","tok":[{"p":"NOUN","l":"Haus"},{"p":"VERB","l":"gehen"},{"p":"PROPN","l":"Bern"}]}],"tsents":[{"lg":"de","tokens":[{"p":"NOUN","l":"Haus"},{"p":"PROPN","t":"Zürich"}]}]}"#;

        let freq = collect(input, "de", &["PROPN", "NOUN"], 2);

        assert_eq!(freq.get("haus"), Some(&2));
        assert_eq!(freq.get("bern"), Some(&1));
        assert_eq!(freq.get("zürich"), Some(&1));
        assert!(!freq.contains_key("gehen"));
    }

    #[test]
    fn filters_by_language_pos_and_min_length() {
        let input = r#"{"sents":[{"lg":"de","tok":[{"p":"NOUN","l":"Ab"},{"p":"NOUN","l":"A"},{"p":"ADJ","l":"Gross"}]},{"lg":"fr","tok":[{"p":"NOUN","l":"Maison"}]}]}"#;

        let freq = collect(input, "de", &["NOUN"], 2);

        assert_eq!(freq.get("ab"), Some(&1));
        assert!(!freq.contains_key("a"));
        assert!(!freq.contains_key("gross"));
        assert!(!freq.contains_key("maison"));
    }

    #[test]
    fn skips_malformed_json_lines() {
        let input = concat!(
            "{\"sents\":[{\"lg\":\"de\",\"tok\":[{\"p\":\"NOUN\",\"l\":\"Zeitung\"}]}]}\n",
            "not json\n",
            "{\"sents\":[{\"lg\":\"de\",\"tok\":[{\"p\":\"NOUN\",\"l\":\"Zeitung\"}]}]}\n"
        );

        let freq = collect(input, "de", &["NOUN"], 2);

        assert_eq!(freq.get("zeitung"), Some(&2));
    }
}
