"""
modules/chamber_monitor.py — Ordered Chamber Enforcement

Derived from the Ordered Chamber Theorem:
  q_1 >= q_2 >= ... > 0  →  all agents produce positive contributions

The chamber monitor checks that agent priorities are properly ordered.
A priority inversion (q_j < q_{j+1}) indicates an agent has left the
safe operating region.

Also provides parity checking: odd/even agent indices have different
expected behavior (from the Parity Law: sign(H_geo) = (-1)^{k+1}).

Author: Feather Research Agent — Vine Mathematics Governance Layer
"""

from __future__ import annotations

import json
import sqlite3
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "chamber_monitor.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_priority (
            agent_id TEXT PRIMARY KEY,
            priority REAL NOT NULL,
            parent_id TEXT,
            depth INTEGER NOT NULL DEFAULT 0,
            parity INTEGER NOT NULL DEFAULT 0,
            chamber_status TEXT NOT NULL DEFAULT 'unchecked',
            last_checked TEXT,
            violation_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ''
        );
        
        CREATE TABLE IF NOT EXISTS chamber_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            agent_id TEXT,
            detail TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def register_agent(
    agent_id: str,
    priority: float,
    *,
    parent_id: Optional[str] = None,
    depth: int = 0,
    db_path: Optional[str] = None,
) -> bool:
    """Register an agent's priority in the chamber."""
    conn = _get_conn(db_path)
    parity = depth % 2  # even depth = 0, odd depth = 1
    conn.execute(
        """INSERT OR REPLACE INTO agent_priority 
           (agent_id, priority, parent_id, depth, parity, chamber_status, last_checked, created_at)
           VALUES (?, ?, ?, ?, ?, 'unchecked', ?, ?)""",
        (agent_id, priority, parent_id, depth, parity,
         datetime.now(timezone.utc).isoformat(),
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    return True


def check_chamber(db_path: Optional[str] = None) -> dict:
    """Check the ordered chamber condition across all agents.
    
    For each parent agent, its children must have non-increasing priorities:
      q_child1 >= q_child2 >= ... > 0
    """
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM agent_priority ORDER BY parent_id, created_at"
    ).fetchall()
    
    violations = []
    agents_checked = 0
    
    # Group by parent
    by_parent = {}
    for r in rows:
        pid = r["parent_id"] or "__root__"
        if pid not in by_parent:
            by_parent[pid] = []
        by_parent[pid].append(dict(r))
    
    # Check ordering within each parent group
    for parent_id, agents in by_parent.items():
        for i in range(len(agents) - 1):
            agents_checked += 1
            # Children of same parent must have non-increasing priorities
            if agents[i]["priority"] < agents[i+1]["priority"]:
                violations.append({
                    "parent": parent_id,
                    "agent_above": agents[i]["agent_id"],
                    "priority_above": agents[i]["priority"],
                    "agent_below": agents[i+1]["agent_id"],
                    "priority_below": agents[i+1]["priority"],
                    "message": f"Priority inversion under {parent_id}: "
                              f"{agents[i]['agent_id']}({agents[i]['priority']}) < "
                              f"{agents[i+1]['agent_id']}({agents[i+1]['priority']})"
                })
                conn.execute(
                    "UPDATE agent_priority SET chamber_status = 'out_of_chamber', "
                    "violation_count = violation_count + 1 WHERE agent_id IN (?, ?)",
                    (agents[i]["agent_id"], agents[i+1]["agent_id"])
                )
    
    # Mark clean agents
    conn.execute(
        "UPDATE agent_priority SET chamber_status = 'in_chamber', "
        "last_checked = ? WHERE chamber_status = 'unchecked'",
        (datetime.now(timezone.utc).isoformat(),)
    )
    
    # Log event
    if violations:
        conn.execute(
            "INSERT INTO chamber_event (timestamp, event_type, detail) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), "violation",
             f"{len(violations)} priority inversions detected")
        )
    else:
        conn.execute(
            "INSERT INTO chamber_event (timestamp, event_type, detail) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), "check_pass", "All priorities ordered")
        )
    
    conn.commit()
    conn.close()
    
    return {
        "status": "in_chamber" if len(violations) == 0 else "violation",
        "agents_checked": agents_checked,
        "violations": len(violations),
        "violation_details": violations,
    }


def check_parity(agent_id: str, db_path: Optional[str] = None) -> dict:
    """Check parity for a specific agent.
    
    Even-depth agents (parity=0) should have balanced behavior.
    Odd-depth agents (parity=1) may exhibit sign alternation.
    """
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM agent_priority WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    conn.close()
    
    if not row:
        return {"agent_id": agent_id, "status": "unknown"}
    
    parity = row["parity"]
    return {
        "agent_id": agent_id,
        "depth": row["depth"],
        "parity": parity,
        "parity_type": "even" if parity == 0 else "odd",
        "expected_behavior": "balanced_signature" if parity == 0 else "alternating_signature",
        "chamber_status": row["chamber_status"],
    }


def get_chamber_status(db_path: Optional[str] = None) -> dict:
    """Get overall chamber status."""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN chamber_status = 'in_chamber' THEN 1 ELSE 0 END) as in_chamber, "
        "SUM(CASE WHEN chamber_status = 'out_of_chamber' THEN 1 ELSE 0 END) as out_of_chamber, "
        "SUM(violation_count) as total_violations "
        "FROM agent_priority"
    ).fetchone()
    conn.close()
    
    total = row["total"] or 0
    in_ch = row["in_chamber"] or 0
    out_ch = row["out_of_chamber"] or 0
    
    return {
        "total_agents": total,
        "in_chamber": in_ch,
        "out_of_chamber": out_ch,
        "total_violations": row["total_violations"] or 0,
        "health": 1.0 if total == 0 else in_ch / total,
        "status": "healthy" if out_ch == 0 else "degraded",
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "chamber_test.db")
    
    try:
        # Register agents at depth 0
        register_agent("agent_A1", 10.0, depth=0, db_path=db)
        register_agent("agent_A2", 8.0, depth=0, db_path=db)
        register_agent("agent_A3", 5.0, depth=0, db_path=db)
        
        # Register agents at depth 1
        register_agent("agent_B1", 7.0, parent_id="agent_A1", depth=1, db_path=db)
        register_agent("agent_B2", 3.0, parent_id="agent_A1", depth=1, db_path=db)
        
        # Check chamber — should pass (all priorities ordered)
        result = check_chamber(db_path=db)
        assert result["status"] == "in_chamber"
        assert result["violations"] == 0
        
        # Create a violation: register child of agent_A1 with priority ABOVE existing child
        # agent_B1 has priority 7.0, so agent_B3 with priority 9.0 under same parent = violation
        register_agent("agent_B3", 9.0, parent_id="agent_A1", depth=1, db_path=db)
        result2 = check_chamber(db_path=db)
        assert result2["status"] == "violation"
        assert result2["violations"] >= 1
        
        # Parity check
        parity = check_parity("agent_A1", db_path=db)
        assert parity["parity_type"] == "even"
        
        parity2 = check_parity("agent_B1", db_path=db)
        assert parity2["parity_type"] == "odd"
        
        # Chamber status
        status = get_chamber_status(db_path=db)
        assert status["total_agents"] == 6
        
        os.remove(db)
        print("  chamber_monitor self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  chamber_monitor self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  chamber_monitor self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
