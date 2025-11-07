// Rust Brain Worker - Heavy numeric operations for AI learning
// Handles: embeddings, similarity search, batch validation
use serde::{Deserialize, Serialize};
use std::io::{self, Read};
use rayon::prelude::*;

#[derive(Deserialize)]
struct Request {
    task: String,
    payload: serde_json::Value,
}

#[derive(Serialize)]
struct Response {
    status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    embeddings: Option<Vec<Vec<f32>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

/// Compute cosine similarity between two vectors
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }

    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        dot / (norm_a * norm_b)
    }
}

/// Generate deterministic pseudo-embeddings (replace with real model later)
fn generate_embedding(text: &str, dim: usize) -> Vec<f32> {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};

    let mut hasher = DefaultHasher::new();
    text.hash(&mut hasher);
    let seed = hasher.finish();

    // Deterministic pseudo-random using simple LCG
    let mut rng = seed;
    let mut emb = Vec::with_capacity(dim);

    for _ in 0..dim {
        rng = rng.wrapping_mul(1103515245).wrapping_add(12345);
        let val = ((rng / 65536) % 1000) as f32 / 1000.0 - 0.5;
        emb.push(val);
    }

    // Normalize
    let norm: f32 = emb.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 0.0 {
        for val in &mut emb {
            *val /= norm;
        }
    }

    emb
}

/// Handle embedding generation task
fn handle_embed_texts(payload: &serde_json::Value) -> Response {
    let texts = match payload.get("texts").and_then(|v| v.as_array()) {
        Some(arr) => arr,
        None => {
            return Response {
                status: "error".to_string(),
                result: None,
                embeddings: None,
                error: Some("Missing 'texts' array in payload".to_string()),
            };
        }
    };

    let dim = payload.get("dim").and_then(|v| v.as_u64()).unwrap_or(128) as usize;

    // Parallel embedding generation
    let embeddings: Vec<Vec<f32>> = texts
        .par_iter()
        .map(|text| {
            let text_str = text.as_str().unwrap_or("");
            generate_embedding(text_str, dim)
        })
        .collect();

    Response {
        status: "ok".to_string(),
        result: None,
        embeddings: Some(embeddings),
        error: None,
    }
}

/// Handle cosine similarity ranking task
fn handle_cosine_rank(payload: &serde_json::Value) -> Response {
    let query = match payload.get("query").and_then(|v| v.as_array()) {
        Some(arr) => {
            let vec: Vec<f32> = arr.iter()
                .filter_map(|v| v.as_f64())
                .map(|f| f as f32)
                .collect();
            vec
        }
        None => {
            return Response {
                status: "error".to_string(),
                result: None,
                embeddings: None,
                error: Some("Missing 'query' array".to_string()),
            };
        }
    };

    let candidates = match payload.get("candidates").and_then(|v| v.as_array()) {
        Some(arr) => arr,
        None => {
            return Response {
                status: "error".to_string(),
                result: None,
                embeddings: None,
                error: Some("Missing 'candidates' array".to_string()),
            };
        }
    };

    let top_k = payload.get("top_k").and_then(|v| v.as_u64()).unwrap_or(5) as usize;

    // Convert candidates to Vec<Vec<f32>>
    let cands: Vec<Vec<f32>> = candidates
        .iter()
        .filter_map(|arr| {
            arr.as_array().map(|inner| {
                inner.iter()
                    .filter_map(|v| v.as_f64())
                    .map(|f| f as f32)
                    .collect()
            })
        })
        .collect();

    // Parallel similarity computation
    let similarities: Vec<f32> = cands
        .par_iter()
        .map(|cand| cosine_similarity(&query, cand))
        .collect();

    // Create indices and sort by similarity (descending)
    let mut indexed: Vec<(usize, f32)> = similarities
        .iter()
        .enumerate()
        .map(|(i, &sim)| (i, sim))
        .collect();

    indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

    let top_indices: Vec<usize> = indexed.iter().take(top_k).map(|(i, _)| *i).collect();
    let top_scores: Vec<f32> = indexed.iter().take(top_k).map(|(_, s)| *s).collect();

    let result = serde_json::json!({
        "indices": top_indices,
        "scores": top_scores
    });

    Response {
        status: "ok".to_string(),
        result: Some(result),
        embeddings: None,
        error: None,
    }
}

/// Handle fragment validation task
fn handle_validate_fragment(payload: &serde_json::Value) -> Response {
    let text = match payload.get("text").and_then(|v| v.as_str()) {
        Some(t) => t,
        None => {
            return Response {
                status: "error".to_string(),
                result: None,
                embeddings: None,
                error: Some("Missing 'text' field".to_string()),
            };
        }
    };

    // Simple validation metrics
    let length_ok = text.len() >= 10 && text.len() <= 10000;
    let has_content = !text.trim().is_empty();

    // Check for suspicious patterns (basic)
    let suspicious = text.contains("rm -rf") ||
                     text.contains("exfiltrate") ||
                     text.contains("bypass");

    let validation_score = if !length_ok || !has_content || suspicious {
        0.0
    } else {
        let length_factor = (text.len() as f32 / 512.0).min(1.0);
        length_factor * 0.8 + 0.2
    };

    let result = serde_json::json!({
        "validation_score": validation_score,
        "length_ok": length_ok,
        "has_content": has_content,
        "suspicious": suspicious
    });

    Response {
        status: "ok".to_string(),
        result: Some(result),
        embeddings: None,
        error: None,
    }
}

/// Main dispatcher
fn handle_request(req: Request) -> Response {
    match req.task.as_str() {
        "embed_texts" => handle_embed_texts(&req.payload),
        "cosine_rank" => handle_cosine_rank(&req.payload),
        "validate_fragment" => handle_validate_fragment(&req.payload),
        other => Response {
            status: "error".to_string(),
            result: None,
            embeddings: None,
            error: Some(format!("Unknown task: {}", other)),
        },
    }
}

fn main() -> io::Result<()> {
    // Read all stdin as JSON request
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;

    let req: Request = match serde_json::from_str(&input) {
        Ok(r) => r,
        Err(e) => {
            let err_resp = Response {
                status: "error".to_string(),
                result: None,
                embeddings: None,
                error: Some(format!("Invalid JSON: {}", e)),
            };
            println!("{}", serde_json::to_string(&err_resp).unwrap());
            return Ok(());
        }
    };

    let resp = handle_request(req);
    println!("{}", serde_json::to_string(&resp).unwrap());

    Ok(())
}

