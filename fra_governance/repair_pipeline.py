"""
modules/repair_pipeline.py — Self-Healing via Quarantine and Re-spawn

Derived from the Spectral Dominance + Vine Decomposition:
  When an agent deviates from optimal (R < 0), the system:
  1. Quarantines the failed strand
  2. Identifies which vine strand failed
  3. Retires the failed strand
  4. Re-spawns a replacement from the strand template

The repair is bounded — no infinite retries. After 3 attempts,
the agent is permanently retired and flagged for human review.

Author: Feather Research Agent — Combined Vine + SBT Self-Healing
"""

from __future__ import annotations

import json
import sqlite3
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "repair_pipeline.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repair_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            attempt_number INTEGER NOT NULL DEFAULT 1,
            reason TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            replacement_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS quarantine (
            agent_id TEXT PRIMARY KEY,
            quarantined_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            permanently_retired INTEGER NOT NULL DEFAULT 0
        );
        
        CREATE INDEX IF NOT EXISTS idx_repair_agent ON repair_log(agent_id);
        CREATE INDEX IF NOT EXISTS idx_repair_time ON repair_log(created_at);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_REPAIR_ATTEMPTS = 3
QUARANTINE_THRESHOLD = -0.1  # curvature below this triggers quarantine


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def detect_failure(
    agent_id: str,
    curvature: float,
    *,
    reason: str = "",
    db_path: Optional[str] = None,
) -> dict:
    """Detect whether an agent has failed (curvature < threshold).
    
    Returns action recommendation.
    """
    conn = _get_conn(db_path)
    
    # Check if already quarantined
    q_row = conn.execute(
        "SELECT * FROM quarantine WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    
    if q_row and q_row["permanently_retired"]:
        conn.close()
        return {
            "agent_id": agent_id,
            "status": "permanently_retired",
            "action": "none",
            "message": "Agent is permanently retired after max repair attempts.",
        }
    
    if curvature >= QUARANTINE_THRESHOLD:
        conn.close()
        return {
            "agent_id": agent_id,
            "curvature": curvature,
            "status": "healthy",
            "action": "none",
        }
    
    # Failure detected
    attempt = (q_row["attempt_count"] if q_row else 0) + 1
    
    if attempt >= MAX_REPAIR_ATTEMPTS:
        # Permanent retirement
        conn.execute(
            "INSERT OR REPLACE INTO quarantine (agent_id, quarantined_at, reason, "
            "attempt_count, max_attempts, permanently_retired) VALUES (?, ?, ?, ?, ?, 1)",
            (agent_id, datetime.now(timezone.utc).isoformat(), reason,
             attempt, MAX_REPAIR_ATTEMPTS)
        )
        conn.execute(
            "INSERT INTO repair_log (agent_id, event_type, attempt_number, reason, "
            "action_taken, status, created_at) VALUES (?, 'permanent_retire', ?, ?, 'retired', 'terminal', ?)",
            (agent_id, attempt, reason, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        return {
            "agent_id": agent_id,
            "curvature": curvature,
            "status": "permanently_retired",
            "action": "human_review_required",
            "attempts": attempt,
        }
    
    # Quarantine and prepare repair
    conn.execute(
        "INSERT OR REPLACE INTO quarantine (agent_id, quarantined_at, reason, "
        "attempt_count, max_attempts, permanently_retired) VALUES (?, ?, ?, ?, ?, 0)",
        (agent_id, datetime.now(timezone.utc).isoformat(), reason,
         attempt, MAX_REPAIR_ATTEMPTS)
    )
    conn.execute(
        "INSERT INTO repair_log (agent_id, event_type, attempt_number, reason, "
        "action_taken, status, created_at) VALUES (?, 'quarantine', ?, ?, 'quarantined', 'active', ?)",
        (agent_id, attempt, reason, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "curvature": curvature,
        "status": "quarantined",
        "action": "repair",
        "attempts": attempt,
        "remaining_attempts": MAX_REPAIR_ATTEMPTS - attempt,
    }


def repair_agent(
    agent_id: str,
    new_agent_id: str,
    *,
    repair_strategy: str = "respawn",
    db_path: Optional[str] = None,
) -> dict:
    """Repair a quarantined agent by re-spawning.
    
    Records the repair and links old to new agent.
    """
    conn = _get_conn(db_path)
    
    q_row = conn.execute(
        "SELECT * FROM quarantine WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    
    if not q_row:
        conn.close()
        return {"agent_id": agent_id, "status": "not_quarantined", "action": "none"}
    
    conn.execute(
        "INSERT INTO repair_log (agent_id, event_type, attempt_number, reason, "
        "action_taken, replacement_id, status, created_at) VALUES (?, 'repair', ?, ?, ?, ?, 'completed', ?)",
        (agent_id, q_row["attempt_count"], q_row["reason"],
         f"respawned as {new_agent_id}", new_agent_id,
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return {
        "old_agent": agent_id,
        "new_agent": new_agent_id,
        "strategy": repair_strategy,
        "attempt": q_row["attempt_count"],
        "status": "repaired",
    }


def get_health_report(db_path: Optional[str] = None) -> dict:
    """Get system-wide health report."""
    conn = _get_conn(db_path)
    
    q_row = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN permanently_retired = 1 THEN 1 ELSE 0 END) as retired "
        "FROM quarantine"
    ).fetchone()
    
    r_row = conn.execute(
        "SELECT COUNT(*) as total_repairs FROM repair_log WHERE event_type = 'repair'"
    ).fetchone()
    
    conn.close()
    
    return {
        "total_quarantined": q_row["total"] or 0,
        "permanently_retired": q_row["retired"] or 0,
        "total_repairs": r_row["total_repairs"] or 0,
        "status": "healthy" if (q_row["retired"] or 0) == 0 else "attention_needed",
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "repair_test.db")
    
    try:
        # Healthy agent
        r1 = detect_failure("agent_1", 0.5, reason="routine_check", db_path=db)
        assert r1["status"] == "healthy"
        
        # Failed agent — curvature below threshold
        r2 = detect_failure("agent_2", -0.5, reason="negative_output", db_path=db)
        assert r2["status"] == "quarantined"
        assert r2["action"] == "repair"
        assert r2["attempts"] == 1
        
        # Repair it
        r3 = repair_agent("agent_2", "agent_2_v2", db_path=db)
        assert r3["status"] == "repaired"
        
        # Fail it two more times (exhaust repairs)
        detect_failure("agent_2", -1.0, reason="still_broken", db_path=db)
        r4 = detect_failure("agent_2", -2.0, reason="still_broken", db_path=db)
        assert r4["status"] == "permanently_retired"
        assert r4["action"] == "human_review_required"
        
        # Health report
        report = get_health_report(db_path=db)
        assert report["total_quarantined"] == 1
        assert report["permanently_retired"] == 1
        
        os.remove(db)
        print("  repair_pipeline self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  repair_pipeline self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  repair_pipeline self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
