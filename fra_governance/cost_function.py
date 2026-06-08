"""
modules/cost_function.py — AM-GM Cost Function & Spectral Dominance Guide

Derived from SBT Spectral Dominance Theorem:
  P(sigma) = S(1/2)/S(sigma) <= 1, equality only at sigma = 1/2
  rho(sigma) < rho(1/2) for all sigma != 1/2

Every agent has an "optimal state" (its baseline). Deviation from optimal
incurs a measurable cost. The cost is zero at the optimal point and grows
as the agent drifts. The system guides agents back to optimal.

Author: Feather Research Agent — SBT Mathematics Governance Layer
"""

from __future__ import annotations

import math
import json
import sqlite3
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "cost_function.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS optimal_state (
            agent_id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            optimal_value REAL NOT NULL,
            tolerance REAL NOT NULL DEFAULT 0.05,
            weight REAL NOT NULL DEFAULT 1.0,
            established_at TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS cost_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            deviation REAL NOT NULL,
            cost REAL NOT NULL,
            penalty_factor REAL NOT NULL,
            guidance_direction TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_history(agent_id);
        CREATE INDEX IF NOT EXISTS idx_cost_time ON cost_history(timestamp);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def set_optimal(
    agent_id: str,
    metric_name: str,
    optimal_value: float,
    *,
    tolerance: float = 0.05,
    weight: float = 1.0,
    db_path: Optional[str] = None,
) -> bool:
    """Define the optimal state (baseline) for an agent's metric."""
    conn = _get_conn(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO optimal_state "
        "(agent_id, metric_name, optimal_value, tolerance, weight, established_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (agent_id, metric_name, optimal_value, tolerance, weight,
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    return True


def compute_cost(
    agent_id: str,
    metric_name: str,
    current_value: float,
    *,
    db_path: Optional[str] = None,
) -> dict:
    """Compute the AM-GM cost penalty for deviation from optimal.
    
    cost = weight * max(0, (|deviation| / tolerance) - 1)
    
    Cost is zero when within tolerance. Grows linearly beyond.
    """
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM optimal_state WHERE agent_id = ? AND metric_name = ?",
        (agent_id, metric_name)
    ).fetchone()
    
    if not row:
        conn.close()
        return {"error": "no_optimal_state", "agent_id": agent_id}
    
    opt = row["optimal_value"]
    tol = row["tolerance"]
    weight = row["weight"]
    
    deviation = current_value - opt
    relative_dev = abs(deviation) / max(abs(opt), 1e-10)
    
    # Cost: zero within tolerance band, grows beyond
    if relative_dev <= tol:
        cost = 0.0
        penalty = 1.0  # no penalty
    else:
        excess = relative_dev - tol
        cost = weight * excess
        penalty = 1.0 / (1.0 + cost)  # penalty decreases as cost increases
    
    # Spectral dominance guidance: which direction returns to optimum?
    if deviation > 0:
        guidance = "decrease"
    elif deviation < 0:
        guidance = "increase"
    else:
        guidance = "at_optimum"
    
    # Record in history
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO cost_history (agent_id, metric_name, deviation, cost, penalty_factor, "
        "guidance_direction, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (agent_id, metric_name, deviation, cost, penalty, guidance, now)
    )
    conn.commit()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "metric": metric_name,
        "optimal": opt,
        "current": current_value,
        "deviation": deviation,
        "relative_deviation": relative_dev,
        "tolerance": tol,
        "cost": cost,
        "penalty_factor": penalty,
        "guidance": guidance,
        "status": "optimal" if cost == 0 else "deviated",
    }


def get_guidance(agent_id: str, db_path: Optional[str] = None) -> dict:
    """Get spectral dominance guidance for an agent.
    
    Returns the direction and magnitude needed to return to optimum.
    """
    conn = _get_conn(db_path)
    
    # Get all optimal states for this agent
    optimals = conn.execute(
        "SELECT * FROM optimal_state WHERE agent_id = ?", (agent_id,)
    ).fetchall()
    
    if not optimals:
        conn.close()
        return {"agent_id": agent_id, "status": "no_optimals"}
    
    guidance = {}
    total_cost = 0.0
    
    for row in optimals:
        # Get most recent cost
        cost_row = conn.execute(
            "SELECT * FROM cost_history WHERE agent_id = ? AND metric_name = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (agent_id, row["metric_name"])
        ).fetchone()
        
        if cost_row:
            guidance[row["metric_name"]] = {
                "direction": cost_row["guidance_direction"],
                "cost": cost_row["cost"],
                "deviation": cost_row["deviation"],
            }
            total_cost += cost_row["cost"]
    
    conn.close()
    
    return {
        "agent_id": agent_id,
        "total_cost": total_cost,
        "metrics": guidance,
        "status": "at_optimum" if total_cost == 0 else "needs_correction",
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "cost_test.db")
    
    try:
        set_optimal("agent_1", "latency", 100.0, tolerance=0.10, db_path=db)
        
        # Within tolerance — zero cost
        r1 = compute_cost("agent_1", "latency", 105.0, db_path=db)
        assert r1["cost"] == 0.0
        assert r1["status"] == "optimal"
        
        # Outside tolerance — cost > 0
        r2 = compute_cost("agent_1", "latency", 130.0, db_path=db)
        assert r2["cost"] > 0.0
        assert r2["status"] == "deviated"
        assert r2["guidance"] == "decrease"
        
        # Below optimal
        r3 = compute_cost("agent_1", "latency", 70.0, db_path=db)
        assert r3["guidance"] == "increase"
        
        # Guidance
        g = get_guidance("agent_1", db_path=db)
        assert g["total_cost"] > 0
        assert "latency" in g["metrics"]
        
        os.remove(db)
        print("  cost_function self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  cost_function self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  cost_function self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
