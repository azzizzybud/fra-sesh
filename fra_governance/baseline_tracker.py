"""
modules/baseline_tracker.py — Geometric Baseline Anomaly Detection

Derived from the Geometric Baseline Theorem:
  R = B - B_geo  (curvature = observed - baseline)
  R >= 0  →  acceptable variation (work being done)
  R < 0   →  anomaly detected

Every agent establishes a "geometric diagonal" — its normal operating
behavior when all priorities are equal (no deviation). The tracker
subtracts the baseline and monitors the curvature remainder.

Also incorporates the SBT spectral dominance principle:
  The system has a unique optimal state at the baseline.
  Deviation produces a measurable penalty proportional to the distance.

Author: Feather Research Agent — Vine + SBT Mathematics Governance Layer
"""

from __future__ import annotations

import json
import sqlite3
import os
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "baseline_tracker.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS baseline (
            agent_id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            baseline_value REAL NOT NULL,
            established_at TEXT NOT NULL,
            sample_count INTEGER NOT NULL DEFAULT 0,
            last_updated TEXT
        );
        
        CREATE TABLE IF NOT EXISTS observation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            observed_value REAL NOT NULL,
            baseline_value REAL NOT NULL,
            curvature REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'normal',
            timestamp TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        );
        
        CREATE INDEX IF NOT EXISTS idx_obs_agent ON observation(agent_id);
        CREATE INDEX IF NOT EXISTS idx_obs_time ON observation(timestamp);
        CREATE INDEX IF NOT EXISTS idx_obs_status ON observation(status);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def establish_baseline(
    agent_id: str,
    metric_name: str,
    baseline_value: float,
    db_path: Optional[str] = None,
) -> bool:
    """Set the geometric baseline (normal operating point) for an agent's metric."""
    conn = _get_conn(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO baseline
           (agent_id, metric_name, baseline_value, established_at, sample_count, last_updated)
           VALUES (?, ?, ?, ?, 1, ?)""",
        (agent_id, metric_name, baseline_value, now, now)
    )
    conn.commit()
    conn.close()
    return True


def observe(
    agent_id: str,
    metric_name: str,
    observed_value: float,
    *,
    note: str = "",
    db_path: Optional[str] = None,
) -> dict:
    """Record an observation and compute the curvature remainder."""
    conn = _get_conn(db_path)
    
    # Get baseline
    row = conn.execute(
        "SELECT baseline_value FROM baseline WHERE agent_id = ? AND metric_name = ?",
        (agent_id, metric_name)
    ).fetchone()
    
    if not row:
        conn.close()
        return {"error": "no_baseline", "agent_id": agent_id, "metric": metric_name}
    
    baseline = row["baseline_value"]
    curvature = observed_value - baseline
    status = "normal" if curvature >= 0 else "anomaly"
    now = datetime.now(timezone.utc).isoformat()
    
    conn.execute(
        """INSERT INTO observation
           (agent_id, metric_name, observed_value, baseline_value, curvature, status, timestamp, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (agent_id, metric_name, observed_value, baseline, curvature, status, now, note)
    )
    
    # Update baseline sample count
    conn.execute(
        "UPDATE baseline SET sample_count = sample_count + 1, last_updated = ? "
        "WHERE agent_id = ? AND metric_name = ?",
        (now, agent_id, metric_name)
    )
    
    conn.commit()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "metric": metric_name,
        "observed": observed_value,
        "baseline": baseline,
        "curvature": curvature,
        "status": status,
    }


def get_agent_health(agent_id: str, db_path: Optional[str] = None) -> dict:
    """Get health report for an agent based on curvature history."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT curvature, status, timestamp FROM observation "
        "WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 100",
        (agent_id,)
    ).fetchall()
    conn.close()
    
    if not rows:
        return {"agent_id": agent_id, "status": "no_data"}
    
    curvatures = [r["curvature"] for r in rows]
    anomalies = sum(1 for r in rows if r["status"] == "anomaly")
    
    # SBT-style penalty: deviation from baseline has a cost
    # P(sigma) = S(1/2)/S(sigma) — the further from baseline, the higher the cost
    mean_curvature = sum(curvatures) / len(curvatures)
    variance = sum((c - mean_curvature)**2 for c in curvatures) / len(curvatures)
    
    return {
        "agent_id": agent_id,
        "observations": len(rows),
        "anomalies": anomalies,
        "anomaly_rate": anomalies / len(rows) if rows else 0,
        "mean_curvature": mean_curvature,
        "curvature_variance": variance,
        "cost_penalty": abs(mean_curvature) + math.sqrt(variance),
        "status": "healthy" if anomalies == 0 else ("degraded" if anomalies < len(rows) * 0.1 else "critical"),
    }


def get_system_health(db_path: Optional[str] = None) -> dict:
    """Get overall system health across all agents."""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status = 'anomaly' THEN 1 ELSE 0 END) as anomalies "
        "FROM observation"
    ).fetchone()
    conn.close()
    
    total = row["total"] or 0
    anomalies = row["anomalies"] or 0
    
    return {
        "total_observations": total,
        "total_anomalies": anomalies,
        "anomaly_rate": anomalies / total if total > 0 else 0,
        "status": "healthy" if anomalies == 0 else ("attention" if anomalies < total * 0.05 else "critical"),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "baseline_test.db")
    
    try:
        establish_baseline("agent_1", "response_time", 100.0, db_path=db)
        
        r1 = observe("agent_1", "response_time", 105.0, note="slightly slow", db_path=db)
        assert r1["status"] == "normal"
        assert r1["curvature"] == 5.0
        
        r2 = observe("agent_1", "response_time", 95.0, note="below baseline", db_path=db)
        assert r2["status"] == "anomaly"
        assert r2["curvature"] == -5.0
        
        r3 = observe("agent_1", "response_time", 110.0, db_path=db)
        assert r3["status"] == "normal"
        
        health = get_agent_health("agent_1", db_path=db)
        assert health["observations"] == 3
        assert health["anomalies"] == 1
        
        sys_health = get_system_health(db_path=db)
        assert sys_health["total_observations"] == 3
        
        os.remove(db)
        print("  baseline_tracker self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  baseline_tracker self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  baseline_tracker self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
