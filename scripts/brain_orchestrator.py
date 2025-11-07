"""
Brain Orchestrator - Neural network learning layer
Coordinates between Python ML and Rust heavy lifting
"""
import json
import subprocess
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import time


class BrainOrchestrator:
    """
    Orchestrates the AI's neural learning:
    - Manages embedding cache
    - Calls Rust worker for heavy ops
    - Handles batching and deduplication
    - Tracks learning artifacts
    """
    
    def __init__(self, 
                 rust_bin: Path = Path("rust-brain/target/release/rust-brain"),
                 cache_dir: Path = Path("brain/cache")):
        self.rust_bin = Path(rust_bin)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.emb_cache_path = self.cache_dir / "embeddings.json"
        self._load_cache()
    
    def _load_cache(self):
        """Load embedding cache from disk."""
        if self.emb_cache_path.exists():
            try:
                with open(self.emb_cache_path, 'r') as f:
                    self._emb_cache = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load embedding cache: {e}")
                self._emb_cache = {}
        else:
            self._emb_cache = {}
    
    def _save_cache(self):
        """Save embedding cache to disk."""
        try:
            with open(self.emb_cache_path, 'w') as f:
                json.dump(self._emb_cache, f)
        except Exception as e:
            print(f"⚠️ Failed to save embedding cache: {e}")
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for cache key."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def call_rust_worker(self, task: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """
        Call Rust worker binary with JSON payload.
        Returns parsed JSON response.
        """
        if not self.rust_bin.exists():
            # Fallback: try debug build
            debug_bin = Path("rust-brain/target/debug/rust-brain")
            if debug_bin.exists():
                self.rust_bin = debug_bin
            else:
                return {
                    "status": "error",
                    "error": f"Rust worker not found at {self.rust_bin}. Run: cd rust-brain && cargo build --release"
                }
        
        request = {"task": task, "payload": payload}
        
        try:
            proc = subprocess.run(
                [str(self.rust_bin)],
                input=json.dumps(request).encode('utf-8'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
            
            if proc.returncode != 0:
                stderr = proc.stderr.decode('utf-8', errors='ignore')
                return {"status": "error", "error": f"Rust worker failed: {stderr}"}
            
            stdout = proc.stdout.decode('utf-8')
            return json.loads(stdout)
            
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Rust worker timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def embed_texts(self, texts: List[str], dim: int = 128, use_cache: bool = True) -> Dict[str, List[float]]:
        """
        Generate embeddings for texts.
        Uses cache to avoid recomputation.
        Returns dict mapping text -> embedding.
        """
        results = {}
        missing = []
        
        for text in texts:
            h = self._hash_text(text)
            cache_key = f"{h}_{dim}"
            
            if use_cache and cache_key in self._emb_cache:
                results[text] = self._emb_cache[cache_key]
            else:
                missing.append(text)
        
        # Batch compute missing embeddings via Rust
        if missing:
            payload = {"texts": missing, "dim": dim}
            response = self.call_rust_worker("embed_texts", payload)
            
            if response.get("status") == "ok" and "embeddings" in response:
                embeddings = response["embeddings"]
                
                for text, emb in zip(missing, embeddings):
                    h = self._hash_text(text)
                    cache_key = f"{h}_{dim}"
                    self._emb_cache[cache_key] = emb
                    results[text] = emb
                
                # Save cache periodically
                self._save_cache()
            else:
                # Fallback: return empty embeddings
                for text in missing:
                    results[text] = [0.0] * dim
        
        return results
    
    def find_similar(self, 
                     query: str, 
                     candidates: List[str], 
                     top_k: int = 5,
                     dim: int = 128) -> List[Dict[str, Any]]:
        """
        Find most similar candidates to query using cosine similarity.
        Returns list of {text, score, index} sorted by similarity.
        """
        # Get embeddings
        all_texts = [query] + candidates
        embeddings = self.embed_texts(all_texts, dim=dim)
        
        query_emb = embeddings.get(query)
        if not query_emb:
            return []
        
        cand_embs = [embeddings.get(c, [0.0]*dim) for c in candidates]
        
        # Call Rust for fast similarity ranking
        payload = {
            "query": query_emb,
            "candidates": cand_embs,
            "top_k": top_k
        }
        
        response = self.call_rust_worker("cosine_rank", payload)
        
        if response.get("status") == "ok" and "result" in response:
            result = response["result"]
            indices = result.get("indices", [])
            scores = result.get("scores", [])
            
            return [
                {
                    "text": candidates[idx],
                    "score": score,
                    "index": idx
                }
                for idx, score in zip(indices, scores)
                if idx < len(candidates)
            ]
        
        return []
    
    def validate_fragment_rust(self, text: str) -> Dict[str, Any]:
        """
        Use Rust worker for basic fragment validation.
        Returns validation metadata.
        """
        payload = {"text": text}
        response = self.call_rust_worker("validate_fragment", payload)
        
        if response.get("status") == "ok" and "result" in response:
            return response["result"]
        
        return {"validation_score": 0.0, "error": response.get("error")}
    
    def clear_cache(self):
        """Clear embedding cache."""
        self._emb_cache = {}
        self._save_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        return {
            "cached_embeddings": len(self._emb_cache),
            "cache_size_bytes": self.emb_cache_path.stat().st_size if self.emb_cache_path.exists() else 0
        }

