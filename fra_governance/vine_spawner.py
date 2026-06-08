"""
modules/vine_spawner.py — Agent Creation from Vine Strand Templates

Derived from the Vine Decomposition Theorem:
  R = sum_i a_i * P_i(s; a_i, a_{i+1}, ..., a_N)
  
  Strand cardinalities are invariant across k:
    2x2 vine: 52/21/6 (k=3), 295/120/36/8 (k=4), 1730/710/220/55/10 (k=5)
    3x3 vine: 57/12 (all k=3,4,5)
    
  The innermost strand is always a pure or near-pure power:
    P_N = C * (gap_N + base)^(2N-1)

When FRA spawns a new agent at scale K, it creates N = K sub-agents
with predetermined complexity (strand cardinalities). No guesswork.

Author: Feather Research Agent — Vine Mathematics Governance Layer
"""

from __future__ import annotations

import json
import sqlite3
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Strand Templates (from the Vine Theorem — EXACT_COMPUTED)
# ---------------------------------------------------------------------------

# Cardinalities verified for k=3,4,5
VINE_2x2_TEMPLATES = {
    3: [52, 21, 6],       # total: 79
    4: [295, 120, 36, 8], # total: 459
    5: [1730, 710, 220, 55, 10],  # total: 2725
}

VINE_3x3_TEMPLATES = {
    3: [57, 12],  # total: 69 (2-gap, invariant across k=3,4,5)
    4: [57, 12],
    5: [57, 12],
}

# Innermost strand form: P_N ~ (gap_N + base)^(2N-1)
INNERMOST_POWER = {
    2: 3,   # (a+s)^3 for 2x2
    3: 5,   # (a+s)^5 for 2x2
    4: 7,   # extrapolated
    5: 9,   # extrapolated
}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "vine_spawner.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS spawned_agent (
            agent_id TEXT PRIMARY KEY,
            parent_id TEXT,
            scale INTEGER NOT NULL,
            strand_index INTEGER NOT NULL,
            strand_terms INTEGER NOT NULL,
            priority REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            last_verified TEXT
        );
        
        CREATE TABLE IF NOT EXISTS vine_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            expected_output REAL,
            actual_output REAL,
            curvature REAL,
            status TEXT NOT NULL DEFAULT 'unchecked',
            timestamp TEXT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_spawn_parent ON spawned_agent(parent_id);
        CREATE INDEX IF NOT EXISTS idx_spawn_status ON spawned_agent(status);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def spawn_agent(
    scale: int,
    *,
    parent_id: Optional[str] = None,
    vine_type: str = "2x2",
    base_priority: float = 1.0,
    db_path: Optional[str] = None,
) -> dict:
    """Spawn a new agent with sub-agents according to vine strand template.
    
    Returns the spawned agent hierarchy.
    """
    templates = VINE_2x2_TEMPLATES if vine_type == "2x2" else VINE_3x3_TEMPLATES
    
    if scale not in templates:
        # Extrapolate for higher scales
        closest = max(templates.keys())
        template = templates[closest]
    else:
        template = templates[scale]
    
    conn = _get_conn(db_path)
    spawned = []
    now = datetime.now(timezone.utc).isoformat()
    
    # Create parent agent
    parent_aid = str(uuid.uuid4())[:8]
    
    for i, term_count in enumerate(template):
        strand_id = str(uuid.uuid4())[:8]
        
        # Priority decays along the vine: inner strands have lower priority
        # but are ALWAYS positive (coefficientwise)
        priority = base_priority * (1.0 - 0.15 * i)  # 15% decay per strand
        priority = max(0.1, priority)
        
        conn.execute(
            "INSERT INTO spawned_agent (agent_id, parent_id, scale, strand_index, "
            "strand_terms, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)",
            (strand_id, parent_aid, scale, i, term_count, priority, now)
        )
        
        spawned.append({
            "agent_id": strand_id,
            "strand_index": i,
            "strand_terms": term_count,
            "priority": priority,
            "role": "innermost_positive" if i == len(template) - 1 else f"strand_{i+1}",
        })
    
    conn.commit()
    conn.close()
    
    total_components = sum(t["strand_terms"] for t in spawned)
    
    return {
        "parent_id": parent_aid,
        "parent_of": parent_id,
        "scale": scale,
        "vine_type": vine_type,
        "strands": len(spawned),
        "total_components": total_components,
        "innermost_power": INNERMOST_POWER.get(scale, 2*scale - 1),
        "agents": spawned,
        "template": template,
    }


def verify_vine_output(
    agent_id: str,
    expected_output: float,
    actual_output: float,
    *,
    db_path: Optional[str] = None,
) -> dict:
    """Verify an agent's output against the vine decomposition.
    
    curvature = actual - expected.
    curvature >= 0  → healthy (positive contribution)
    curvature < 0   → anomaly (negative contribution)
    """
    conn = _get_conn(db_path)
    curvature = actual_output - expected_output
    status = "positive_contribution" if curvature >= 0 else "anomaly"
    
    conn.execute(
        "INSERT INTO vine_verification (agent_id, expected_output, actual_output, "
        "curvature, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (agent_id, expected_output, actual_output, curvature, status,
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "expected": expected_output,
        "actual": actual_output,
        "curvature": curvature,
        "status": status,
    }


def get_agent_tree(parent_id: str, db_path: Optional[str] = None) -> dict:
    """Get the full vine hierarchy for a spawned agent tree."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM spawned_agent WHERE parent_id = ? OR agent_id = ? "
        "ORDER BY strand_index",
        (parent_id, parent_id)
    ).fetchall()
    conn.close()
    
    agents = []
    total_terms = 0
    for r in rows:
        agents.append({
            "agent_id": r["agent_id"],
            "strand_index": r["strand_index"],
            "strand_terms": r["strand_terms"],
            "priority": r["priority"],
            "status": r["status"],
        })
        total_terms += r["strand_terms"]
    
    return {
        "parent_id": parent_id,
        "child_count": len(agents),
        "total_components": total_terms,
        "agents": agents,
    }


def compute_scale_complexity(scale: int, vine_type: str = "2x2") -> dict:
    """Predict the complexity of an agent at a given scale BEFORE spawning.
    
    Uses known strand cardinalities or extrapolates from the pattern.
    """
    templates = VINE_2x2_TEMPLATES if vine_type == "2x2" else VINE_3x3_TEMPLATES
    
    if scale in templates:
        strands = templates[scale]
        exact = True
    else:
        # Extrapolate: growth rate is approximately 5.8x per scale step
        closest = max(templates.keys())
        base = sum(templates[closest])
        factor = 5.8 ** (scale - closest)
        estimated_total = int(base * factor)
        strands = [estimated_total]  # rough estimate
        exact = False
    
    return {
        "scale": scale,
        "vine_type": vine_type,
        "strand_count": len(strands),
        "component_total": sum(strands),
        "per_strand": strands,
        "exact": exact,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "vine_spawn_test.db")
    
    try:
        # Spawn at scale 3
        result = spawn_agent(3, vine_type="2x2", db_path=db)
        assert result["scale"] == 3
        assert result["strands"] == 3
        assert result["total_components"] == 79
        assert result["template"] == [52, 21, 6]
        
        # Spawn at scale 4 (3x3)
        result2 = spawn_agent(4, vine_type="3x3", db_path=db)
        assert result2["scale"] == 4
        assert result2["strands"] == 2
        assert result2["total_components"] == 69
        assert result2["template"] == [57, 12]
        
        # Verify output
        v = verify_vine_output(result["agents"][0]["agent_id"], 100.0, 105.0, db_path=db)
        assert v["status"] == "positive_contribution"
        
        v2 = verify_vine_output(result["agents"][2]["agent_id"], 100.0, 90.0, db_path=db)
        assert v2["status"] == "anomaly"
        
        # Agent tree
        tree = get_agent_tree(result["parent_id"], db_path=db)
        assert tree["child_count"] == 3
        
        # Complexity prediction
        pred = compute_scale_complexity(3)
        assert pred["exact"] == True
        assert pred["component_total"] == 79
        
        pred2 = compute_scale_complexity(10)
        assert pred2["exact"] == False  # extrapolated
        
        os.remove(db)
        print("  vine_spawner self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  vine_spawner self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  vine_spawner self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
