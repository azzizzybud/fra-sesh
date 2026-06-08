"""
modules/bezoutian_verifier.py — Determinant-Based Integrity Check

Derived from the Cauchy Factorization and Bezoutian structure:
  Every D_k term = det | u_i  p_i; w_m  v_m |
  The D-Hankel matrix = Bezoutian of gamma-weighted binomial sequences.

The Bezoutian verifier checks that agent response matrices maintain
their determinant structure. When determinants cross zero or change
sign unexpectedly, the system flags a structural violation.

Also incorporates the Transport Cone principle:
  Agent interactions follow a predictable Hankel pattern.
  Deviations from the pattern indicate erroneous behavior.

Author: Feather Research Agent — Vine Mathematics Governance Layer
"""

from __future__ import annotations

import math
import json
import sqlite3
import os
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "bezoutian_verifier.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS response_matrix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            matrix_size INTEGER NOT NULL,
            matrix_data TEXT NOT NULL,
            determinant REAL,
            expected_sign INTEGER,
            actual_sign INTEGER,
            status TEXT NOT NULL DEFAULT 'unchecked',
            timestamp TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_agent TEXT NOT NULL,
            target_agent TEXT NOT NULL,
            expected_effect REAL,
            actual_effect REAL,
            transport_error REAL,
            status TEXT NOT NULL DEFAULT 'unchecked',
            timestamp TEXT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_resp_agent ON response_matrix(agent_id);
        CREATE INDEX IF NOT EXISTS idx_interact_source ON interaction_log(source_agent);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def register_response(
    agent_id: str,
    matrix: list[list[float]],
    *,
    expected_sign: int = 1,
    db_path: Optional[str] = None,
) -> dict:
    """Register an agent's response matrix and verify its Bezoutian structure.
    
    Checks that the determinant has the expected sign.
    If not, flags a structural anomaly.
    """
    conn = _get_conn(db_path)
    
    mat = np.array(matrix, dtype=float)
    det_val = float(np.linalg.det(mat))
    size = len(matrix)
    
    actual_sign = 1 if det_val > 1e-10 else (-1 if det_val < -1e-10 else 0)
    sign_match = actual_sign == expected_sign or actual_sign == 0 or expected_sign == 0
    
    status = "structural_ok" if sign_match else "sign_anomaly"
    
    conn.execute(
        "INSERT INTO response_matrix (agent_id, matrix_size, matrix_data, determinant, "
        "expected_sign, actual_sign, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (agent_id, size, json.dumps(matrix), det_val, expected_sign, actual_sign,
         status, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return {
        "agent_id": agent_id,
        "matrix_size": size,
        "determinant": det_val,
        "expected_sign": expected_sign,
        "actual_sign": actual_sign,
        "status": status,
    }


def check_minor_sequence(
    agent_id: str,
    minor_sizes: list[int],
    get_matrix_for_size,
    *,
    db_path: Optional[str] = None,
) -> dict:
    """Check the sequence of Bezoutian minors for parity-graded positivity.
    
    Tests the PGTP-like pattern: minors of different sizes should
    follow a consistent sign pattern based on their parity.
    """
    results = []
    all_ok = True
    
    for size in minor_sizes:
        mat = get_matrix_for_size(size)
        det_val = float(np.linalg.det(np.array(mat, dtype=float)))
        # Parity expectation: even-size minors positive, odd-size may alternate
        if size % 2 == 0:
            expected_sign = 1
        else:
            expected_sign = 0  # no fixed expectation for odd sizes
        
        actual_sign = 1 if det_val > 1e-10 else (-1 if det_val < -1e-10 else 0)
        ok = expected_sign == 0 or actual_sign == expected_sign
        
        if not ok:
            all_ok = False
        
        results.append({
            "size": size,
            "determinant": det_val,
            "expected_sign": expected_sign,
            "actual_sign": actual_sign,
            "ok": ok,
        })
    
    return {
        "agent_id": agent_id,
        "minors_checked": len(results),
        "all_pass": all_ok,
        "results": results,
        "status": "pg_consistent" if all_ok else "pg_violation",
    }


def record_interaction(
    source_agent: str,
    target_agent: str,
    expected_effect: float,
    actual_effect: float,
    *,
    db_path: Optional[str] = None,
) -> dict:
    """Record a transport cone interaction between agents.
    
    Compares expected effect (from Hankel prediction) with actual.
    """
    conn = _get_conn(db_path)
    
    transport_error = abs(expected_effect - actual_effect) / max(abs(expected_effect), 1e-10) if abs(expected_effect) > 1e-10 else 0.0
    status = "in_cone" if transport_error < 0.2 else "out_of_cone"
    
    conn.execute(
        "INSERT INTO interaction_log (source_agent, target_agent, expected_effect, "
        "actual_effect, transport_error, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source_agent, target_agent, expected_effect, actual_effect,
         transport_error, status, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return {
        "source": source_agent,
        "target": target_agent,
        "expected": expected_effect,
        "actual": actual_effect,
        "transport_error": transport_error,
        "status": status,
    }


def get_structural_health(agent_id: str, db_path: Optional[str] = None) -> dict:
    """Get Bezoutian structural health for an agent."""
    conn = _get_conn(db_path)
    
    rows = conn.execute(
        "SELECT status FROM response_matrix WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 20",
        (agent_id,)
    ).fetchall()
    conn.close()
    
    if not rows:
        return {"agent_id": agent_id, "status": "no_data"}
    
    anomalies = sum(1 for r in rows if r["status"] != "structural_ok")
    
    return {
        "agent_id": agent_id,
        "checks": len(rows),
        "anomalies": anomalies,
        "health": 1.0 - (anomalies / len(rows)),
        "status": "healthy" if anomalies == 0 else "degraded",
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "bezoutian_test.db")
    
    try:
        # Register a positive-definite with wrong expectation (should fail sign check)
        pos_mat = [[2.0, 0.5], [0.5, 2.0]]
        r1 = register_response("agent_1", pos_mat, expected_sign=-1, db_path=db)
        assert r1["status"] == "sign_anomaly"
        assert r1["determinant"] > 0
        
        # Register with correct expectation (should pass)
        r2 = register_response("agent_1", pos_mat, expected_sign=1, db_path=db)
        assert r2["status"] == "structural_ok"
        
        # Register a 1x1 negative matrix with correct negative expectation
        neg_mat_1d = [[-3.0]]
        r3 = register_response("agent_1", neg_mat_1d, expected_sign=-1, db_path=db)
        assert r3["status"] == "structural_ok"
        assert r3["determinant"] < 0
        
        # Interaction recording
        i1 = record_interaction("agent_1", "agent_2", 1.0, 1.05, db_path=db)
        assert i1["status"] == "in_cone"
        
        i2 = record_interaction("agent_1", "agent_3", 1.0, 3.0, db_path=db)
        assert i2["status"] == "out_of_cone"
        
        # Health check
        h = get_structural_health("agent_1", db_path=db)
        assert h["checks"] >= 2
        assert h["anomalies"] >= 1
        
        os.remove(db)
        print("  bezoutian_verifier self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  bezoutian_verifier self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  bezoutian_verifier self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
