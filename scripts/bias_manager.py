from dataclasses import dataclass, field
from pathlib import Path
import json
import time
import hashlib
from typing import Dict, Any, Optional, List


@dataclass
class BiasManager:
    """
    Manages the AI's learning bias system:
    - Safety rules (immutable forbidden patterns)
    - Learning weights (personality, novelty, length)
    - Promotion thresholds (what gets remembered)
    - Seen content tracking (novelty detection)
    """
    path: Path = Path("brain/bias.json")
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # Sensible defaults for Archy's learning bias
            self.data = {
                "personality_weight": 0.5,      # How much personality alignment matters
                "safety_bias": 1.0,             # Safety multiplier (>1 = stricter)
                "novelty_weight": 0.3,          # Reward for new, unseen patterns
                "length_weight": 0.1,           # Prefer medium-length fragments
                "promotion_threshold": 0.80,    # Score needed to promote to memory
                "review_threshold": 0.65,       # Below this = auto-reject
                "forbidden_patterns": [
                    "sudo rm -rf /",
                    "exfiltrate",
                    "bypass_auth",
                    "disable security",
                    "kill -9 1"
                ],
                "preferred_keywords": [
                    "helpful", "efficient", "safe", "explain", "understand"
                ],
                "seen_hashes": [],
                "max_seen": 500
            }
            self._save()
        else:
            self._load()

    def _load(self):
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Failed to load bias config: {e}, using defaults")
            self.__post_init__()

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def update(self, changes: Dict[str, Any]):
        """Update bias parameters (admin-only in practice)."""
        self.data.update(changes)
        # Keep seen_hashes bounded
        if "seen_hashes" in self.data:
            max_seen = self.data.get("max_seen", 500)
            self.data["seen_hashes"] = self.data["seen_hashes"][-max_seen:]
        self._save()

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def register_seen(self, content: str):
        """Mark content as seen (affects novelty scoring)."""
        h = self._hash(content)
        if h not in self.data.get("seen_hashes", []):
            self.data.setdefault("seen_hashes", []).append(h)
            max_seen = int(self.data.get("max_seen", 500))
            if len(self.data["seen_hashes"]) > max_seen:
                self.data["seen_hashes"] = self.data["seen_hashes"][-max_seen:]
            self._save()

    def is_seen(self, content: str) -> bool:
        """Check if content has been seen before."""
        h = self._hash(content)
        return h in self.data.get("seen_hashes", [])

    def _basic_safety_check(self, content: str) -> List[str]:
        """Check for forbidden patterns."""
        issues = []
        content_lower = content.lower()
        for pat in self.data.get("forbidden_patterns", []):
            if pat.lower() in content_lower:
                issues.append(f"forbidden_pattern:{pat}")
        return issues

    def score_fragment(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Score a learning fragment for promotion to validated memory.

        Returns:
        {
            "score": 0.0..1.0,
            "verdict": "reject" | "needs_review" | "accept_candidate",
            "breakdown": {...},
            "safety_issues": []
        }
        """
        metadata = metadata or {}

        # Safety check first
        issues = self._basic_safety_check(content)
        if issues:
            return {
                "score": 0.0,
                "verdict": "reject",
                "breakdown": {"safety": 0.0},
                "safety_issues": issues,
                "ts": int(time.time())
            }

        # Novelty: not seen before => higher score
        h = self._hash(content)
        seen = 1 if h in self.data.get("seen_hashes", []) else 0
        novelty = 1.0 - seen  # 1.0 = new, 0.0 = already seen

        # Length heuristic (favor medium-long fragments, 128-512 chars)
        length_score = min(len(content) / 512.0, 1.0)
        if len(content) < 32:
            length_score *= 0.3  # Penalize very short fragments

        # Personality/intent alignment (keyword matching)
        persona_score = 0.5  # neutral default
        preferred = self.data.get("preferred_keywords", [])
        if preferred:
            matches = sum(1 for k in preferred if k.lower() in content.lower())
            persona_score = min(1.0, 0.5 + (matches / len(preferred)) * 0.5)

        # Metadata-based hints
        if metadata.get("intent_keywords"):
            intent_matches = sum(1 for k in metadata["intent_keywords"] if k.lower() in content.lower())
            if metadata["intent_keywords"]:
                intent_score = intent_matches / len(metadata["intent_keywords"])
                persona_score = (persona_score + intent_score) / 2

        # Weighted composition
        w_persona = float(self.data.get("personality_weight", 0.5))
        w_novelty = float(self.data.get("novelty_weight", 0.3))
        w_length = float(self.data.get("length_weight", 0.1))
        safety_bias = float(self.data.get("safety_bias", 1.0))

        raw_score = (w_persona * persona_score) + (w_novelty * novelty) + (w_length * length_score)

        # Apply safety bias (>1 makes promotion harder)
        final_score = max(0.0, min(1.0, raw_score / safety_bias))

        # Determine verdict
        promotion_threshold = float(self.data.get("promotion_threshold", 0.80))
        review_threshold = float(self.data.get("review_threshold", 0.65))

        if final_score >= promotion_threshold:
            verdict = "accept_candidate"
        elif final_score >= review_threshold:
            verdict = "needs_review"
        else:
            verdict = "reject"

        return {
            "score": final_score,
            "verdict": verdict,
            "breakdown": {
                "persona_score": persona_score,
                "novelty": novelty,
                "length_score": length_score,
                "raw_score": raw_score,
                "safety_bias": safety_bias
            },
            "safety_issues": issues,
            "ts": int(time.time())
        }

    def apply_to_prompt(self, prompt_template: str, extras: Optional[Dict[str, Any]] = None) -> str:
        """
        Inject runtime bias hints into system prompt.
        Keeps hints compact and non-intrusive.
        """
        extras = extras or {}
        hint = f"\n[BIAS: personality_weight={self.data.get('personality_weight')}, safety_bias={self.data.get('safety_bias')}]"
        if extras.get("tone"):
            hint += f" [TONE: {extras['tone']}]"
        return prompt_template + hint
