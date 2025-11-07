"""
MemoryManager - Two-tier learning memory system
- staging_experiences: Testing ground for new learning
- validated_memories: Promoted, reliable memories that define the AI
"""

from pathlib import Path
import sqlite3
import json
import time
from typing import Optional, Dict, Any, List
from bias_manager import BiasManager


class MemoryManager:
    """
    Two-tier memory architecture:

    1. STAGING TABLE (testing ground):
       - All new experiences go here first
       - Run pattern matching, safety checks, scoring
       - Can be bulk-processed, experimented on

    2. VALIDATED MEMORIES (the AI's "self"):
       - Only promoted fragments live here
       - This is what the AI relies on for decisions
       - Versioned, provenance-tracked, auditable
       - Defines "who the AI is" and "why it's here"
    """

    def __init__(self, db_path: Path = Path("brain/brain.db"), bias_manager: Optional[BiasManager] = None):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.bias_manager = bias_manager or BiasManager()
        self._ensure_db()

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def _ensure_db(self):
        """Create the two-tier table structure."""
        conn = self._conn()
        c = conn.cursor()

        # STAGING: testing ground for learning
        c.execute("""
        CREATE TABLE IF NOT EXISTS staging_experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            validator_result TEXT,
            promoted INTEGER DEFAULT 0
        )""")

        # VALIDATED: the AI's reliable memory (its "self")
        c.execute("""
        CREATE TABLE IF NOT EXISTS validated_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            content TEXT NOT NULL,
            provenance TEXT NOT NULL,
            meta TEXT,
            retired INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1
        )""")

        # Create indices for performance
        c.execute("CREATE INDEX IF NOT EXISTS idx_staging_ts ON staging_experiences(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_staging_promoted ON staging_experiences(promoted)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_validated_ts ON validated_memories(ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_validated_retired ON validated_memories(retired)")

        conn.commit()
        conn.close()

    def stage_experience(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add new experience to staging table.
        This is the entry point for all learning.
        """
        ts = int(time.time())
        conn = self._conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO staging_experiences (ts, role, content, metadata) VALUES (?, ?, ?, ?)",
            (ts, role, content, json.dumps(metadata or {}))
        )
        conn.commit()
        rowid = c.lastrowid
        conn.close()
        return rowid

    def list_staged(self, limit: int = 100, unpromoted_only: bool = True) -> List[Dict[str, Any]]:
        """List experiences in staging (optionally filter to unpromoted only)."""
        conn = self._conn()
        c = conn.cursor()

        if unpromoted_only:
            c.execute(
                "SELECT id, ts, role, content, metadata, validator_result, promoted "
                "FROM staging_experiences WHERE promoted = 0 ORDER BY ts DESC LIMIT ?",
                (limit,)
            )
        else:
            c.execute(
                "SELECT id, ts, role, content, metadata, validator_result, promoted "
                "FROM staging_experiences ORDER BY ts DESC LIMIT ?",
                (limit,)
            )

        rows = c.fetchall()
        conn.close()

        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "ts": r[1],
                "role": r[2],
                "content": r[3],
                "metadata": json.loads(r[4] or "{}"),
                "validator_result": json.loads(r[5]) if r[5] else None,
                "promoted": bool(r[6])
            })
        return out

    def validate_and_promote(self, staging_id: int, admin_approve: bool = False) -> Dict[str, Any]:
        """
        Run validator on a staged experience.
        If verdict is "accept_candidate" or admin approves, promote to validated_memories.

        Returns: {"status": "promoted" | "rejected" | "needs_review", ...}
        """
        conn = self._conn()
        c = conn.cursor()
        c.execute("SELECT content, metadata, promoted FROM staging_experiences WHERE id = ?", (staging_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            return {"status": "error", "reason": "staging_id_not_found"}

        content, metadata_json, already_promoted = row[0], row[1], row[2]

        if already_promoted:
            conn.close()
            return {"status": "error", "reason": "already_promoted"}

        metadata = json.loads(metadata_json or "{}")

        # Run bias manager validation
        result = self.bias_manager.score_fragment(content, metadata)

        # Store validator result on staging row
        c.execute(
            "UPDATE staging_experiences SET validator_result = ? WHERE id = ?",
            (json.dumps(result), staging_id)
        )
        conn.commit()

        if result["verdict"] == "reject" and not admin_approve:
            conn.close()
            return {"status": "rejected", "validator": result}

        if result["verdict"] == "accept_candidate" or admin_approve or result["score"] >= 0.8:
            # PROMOTE to validated_memories
            prov = {
                "staging_id": staging_id,
                "ts": int(time.time()),
                "validator_score": result["score"]
            }
            meta = {
                "validator": result,
                "original_meta": metadata
            }

            c.execute(
                "INSERT INTO validated_memories (ts, content, provenance, meta) VALUES (?, ?, ?, ?)",
                (int(time.time()), content, json.dumps(prov), json.dumps(meta))
            )

            # Mark as promoted in staging
            c.execute("UPDATE staging_experiences SET promoted = 1 WHERE id = ?", (staging_id,))

            conn.commit()
            mem_id = c.lastrowid

            # Register as seen in bias manager
            self.bias_manager.register_seen(content)

            conn.close()
            return {
                "status": "promoted",
                "memory_id": mem_id,
                "validator": result
            }

        conn.close()
        return {"status": "needs_review", "validator": result}

    def batch_validate_and_promote(self, limit: int = 50) -> Dict[str, Any]:
        """
        Process batch of unpromoted staging items.
        Auto-promote those that pass threshold.
        Returns summary stats.
        """
        staged = self.list_staged(limit=limit, unpromoted_only=True)

        stats = {
            "processed": 0,
            "promoted": 0,
            "rejected": 0,
            "needs_review": 0
        }

        for item in staged:
            result = self.validate_and_promote(item["id"])
            stats["processed"] += 1

            if result["status"] == "promoted":
                stats["promoted"] += 1
            elif result["status"] == "rejected":
                stats["rejected"] += 1
            elif result["status"] == "needs_review":
                stats["needs_review"] += 1

        return stats

    def list_memories(self, include_retired: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        """List validated memories (the AI's reliable knowledge)."""
        conn = self._conn()
        c = conn.cursor()

        if include_retired:
            query = "SELECT id, ts, content, provenance, meta, retired FROM validated_memories ORDER BY ts DESC LIMIT ?"
        else:
            query = "SELECT id, ts, content, provenance, meta, retired FROM validated_memories WHERE retired=0 ORDER BY ts DESC LIMIT ?"

        c.execute(query, (limit,))
        rows = c.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "ts": r[1],
                "content": r[2],
                "provenance": json.loads(r[3]),
                "meta": json.loads(r[4]),
                "retired": bool(r[5])
            }
            for r in rows
        ]

    def retire_memory(self, memory_id: int, reason: str = "") -> bool:
        """Soft-delete a memory (mark as retired)."""
        conn = self._conn()
        c = conn.cursor()

        # Get current meta to append retire reason
        c.execute("SELECT meta FROM validated_memories WHERE id = ?", (memory_id,))
        row = c.fetchone()
        if row:
            meta = json.loads(row[0] or "{}")
            meta["retired_reason"] = reason
            meta["retired_ts"] = int(time.time())

            c.execute(
                "UPDATE validated_memories SET retired=1, meta=? WHERE id = ?",
                (json.dumps(meta), memory_id)
            )
            conn.commit()
            changed = c.rowcount > 0
        else:
            changed = False

        conn.close()
        return changed

    def decay_old_memories(self, max_age_seconds: int = 60*60*24*30):
        """Auto-retire memories older than threshold (default 30 days)."""
        cutoff = int(time.time()) - max_age_seconds
        conn = self._conn()
        c = conn.cursor()
        c.execute("UPDATE validated_memories SET retired=1 WHERE ts < ? AND retired=0", (cutoff,))
        count = c.rowcount
        conn.commit()
        conn.close()
        return count

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""
        conn = self._conn()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM staging_experiences WHERE promoted=0")
        staging_unpromoted = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM staging_experiences WHERE promoted=1")
        staging_promoted = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM validated_memories WHERE retired=0")
        active_memories = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM validated_memories WHERE retired=1")
        retired_memories = c.fetchone()[0]

        conn.close()

        return {
            "staging": {
                "unpromoted": staging_unpromoted,
                "promoted": staging_promoted,
                "total": staging_unpromoted + staging_promoted
            },
            "validated": {
                "active": active_memories,
                "retired": retired_memories,
                "total": active_memories + retired_memories
            }
        }
