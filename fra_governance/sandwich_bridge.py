"""
fra_governance/sandwich_bridge.py -- FRA Sesh <-> FRA Governance Bridge

Connects FRA Sesh (built on Odysseus) to FRA's Vine/SBT mathematical governance.
Registers FRA Sesh as an external AI system and applies the full sandwich
transformation (7 X-layers of governance checks) to every agent action.

GAMMA layer (raw truth) → X layer (governance) → D layer (structured output)

Author: FRA Sesh + FRA Integration
"""
from __future__ import annotations

import json
import sqlite3
import os
import uuid
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fra_governance.cauchy_ledger import record as ledger_record, verify_agent
from fra_governance.chamber_monitor import register_agent as chamber_register, check_chamber, check_parity
from fra_governance.baseline_tracker import establish_baseline, observe as baseline_observe, get_agent_health
from fra_governance.cost_function import set_optimal, compute_cost, get_guidance
from fra_governance.bezoutian_verifier import register_response, record_interaction
from fra_governance.repair_pipeline import detect_failure


def _data_dir() -> str:
    base = os.environ.get("ODYSSEUS_DATA_DIR", os.environ.get("AGENT_DATA_DIR", "data"))
    Path(base).mkdir(parents=True, exist_ok=True)
    return base


def _db_path() -> str:
    return os.path.join(_data_dir(), "sandwich_bridge.db")


def _get_conn(db_path: Optional[str] = None):
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS connected_system (
            system_id TEXT PRIMARY KEY,
            system_name TEXT NOT NULL,
            system_type TEXT NOT NULL DEFAULT 'external_ai',
            api_endpoint TEXT,
            auth_hash TEXT NOT NULL,
            trust_level TEXT NOT NULL DEFAULT 'amber',
            chamber_depth INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL,
            last_seen TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS session_log (
            id TEXT PRIMARY KEY,
            system_id TEXT NOT NULL,
            session_type TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            gamma_state TEXT NOT NULL,
            x_transforms TEXT NOT NULL,
            d_output TEXT NOT NULL,
            chamber_verdict TEXT NOT NULL,
            ledger_entry_id TEXT,
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sb_session_system ON session_log(system_id);
        CREATE INDEX IF NOT EXISTS idx_sb_session_time ON session_log(timestamp);
    """)
    conn.commit()
    return conn


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class GammaState:
    system_id: str
    metrics: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    priority: float = 1.0
    parity: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class XTransform:
    chamber_check: dict = field(default_factory=dict)
    baseline_deviations: list = field(default_factory=list)
    cost_assessment: dict = field(default_factory=dict)
    bezoutian_status: dict = field(default_factory=dict)
    ledger_entries: list = field(default_factory=list)
    failure_flags: list = field(default_factory=list)


@dataclass
class DOutput:
    system_id: str
    status: str = "ok"
    evidence_level: str = "assumption"
    actions_allowed: list = field(default_factory=list)
    actions_blocked: list = field(default_factory=list)
    guidance: dict = field(default_factory=dict)
    cost: float = 0.0
    warnings: list = field(default_factory=list)


# ── Registration ────────────────────────────────────────────────────────────

def register_fra_sesh(
    system_name: str = "FRA Sesh",
    trust_level: str = "amber",
    chamber_depth: int = 0,
    db_path: Optional[str] = None,
) -> dict:
    """Register FRA Sesh as an FRA-governed external AI system."""
    conn = _get_conn(db_path)
    system_id = str(uuid.uuid4())[:12]
    auth_token = str(uuid.uuid4())
    auth_hash = hashlib.sha256(auth_token.encode()).hexdigest()

    conn.execute(
        "INSERT INTO connected_system (system_id, system_name, system_type, api_endpoint, "
        "auth_hash, trust_level, chamber_depth, registered_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
        (system_id, system_name, "ai_workspace", None, auth_hash,
         trust_level, chamber_depth, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

    chamber_register(system_id, priority=1.0, depth=chamber_depth)

    return {
        "system_id": system_id,
        "auth_token": auth_token,
        "system_name": system_name,
        "trust_level": trust_level,
    }


# ── The Sandwich Transformation ─────────────────────────────────────────────

def _transform(state: GammaState, db_path: Optional[str] = None) -> tuple[XTransform, DOutput]:
    """Apply all 7 governance X-layers to an Odysseus agent state."""
    xform = XTransform()
    output = DOutput(system_id=state.system_id)

    # X1: Ordered Chamber
    chamber_result = check_chamber(db_path=db_path)
    xform.chamber_check = chamber_result
    if chamber_result.get("status") == "violation":
        output.warnings.append(f"Chamber violation: {chamber_result.get('violations', 0)} inversions")
        output.status = "degraded"

    # X2: Parity
    parity_result = check_parity(state.system_id, db_path=db_path)
    if parity_result.get("status") != "unknown":
        state.parity = parity_result.get("parity", 0)

    # X3: Baseline Anomaly Detection
    for metric_name, value in state.metrics.items():
        obs = baseline_observe(state.system_id, metric_name, value, db_path=db_path)
        if obs.get("status") == "anomaly":
            xform.baseline_deviations.append(obs)
            output.warnings.append(f"Anomaly: {metric_name}={value}, curvature={obs.get('curvature', 0):.3f}")
        curvature = obs.get("curvature", 0)
        if curvature < -0.1:
            failure = detect_failure(state.system_id, curvature, reason=f"{metric_name}_anomaly", db_path=db_path)
            xform.failure_flags.append(failure)
            if failure["status"] == "permanently_retired":
                output.status = "blocked"
                output.actions_blocked.append("all")

    # X4: Cost Assessment
    total_cost = 0.0
    for metric_name, value in state.metrics.items():
        cost_info = compute_cost(state.system_id, metric_name, value, db_path=db_path)
        if "error" not in cost_info:
            total_cost += cost_info.get("cost", 0)
    xform.cost_assessment = {"total_cost": total_cost}
    output.cost = total_cost

    # X5: Bezoutian Structural Check
    if "response_matrix" in state.metadata:
        try:
            mat = state.metadata["response_matrix"]
            bz_result = register_response(state.system_id, mat, db_path=db_path)
            xform.bezoutian_status = bz_result
            if bz_result["status"] == "sign_anomaly":
                output.warnings.append("Bezoutian sign anomaly detected")
        except Exception:
            pass
    else:
        xform.bezoutian_status = {"status": "no_matrix_provided"}

    # X6: Cauchy Ledger Recording
    for action in state.actions:
        source = action.get("source", f"{state.system_id}_action")
        flow = action.get("flow", "output")
        loss = action.get("loss", "none")
        balance = action.get("balance", 1.0)
        entry_id = ledger_record(
            state.system_id,
            action.get("type", "external_action"),
            source, flow, loss,
            balance=balance,
            evidence_level="runtime_success",
            provenance="external_data",
            parity=state.parity,
            db_path=db_path,
        )
        xform.ledger_entries.append(entry_id)
        if balance < 0:
            output.actions_blocked.append(action.get("type", "unknown"))
            output.warnings.append(f"Negative balance: {action.get('type', 'unknown')}")
        else:
            output.actions_allowed.append(action.get("type", "unknown"))

    # X7: Guidance
    guidance = get_guidance(state.system_id, db_path=db_path)
    output.guidance = guidance

    # Final verdict
    if output.status == "blocked":
        output.evidence_level = "test_success"
    elif output.warnings:
        output.status = "warning"
        output.evidence_level = "runtime_success"
    else:
        output.status = "ok"
        output.evidence_level = "runtime_success"

    return xform, output


def process_request(
    system_id: str,
    raw_state: dict,
    db_path: Optional[str] = None,
) -> dict:
    """Main entry point: process an Odysseus agent action through governance.

    raw_state = {
        "metrics": {"rounds": 3, "tool_calls": 5, ...},
        "actions": [{"type": "bash", "source": "agent", "flow": "output", "loss": "cpu", "balance": 1.0}],
        "metadata": {}
    }
    """
    conn = _get_conn(db_path)
    sys_row = conn.execute(
        "SELECT * FROM connected_system WHERE system_id = ? AND status = 'active'",
        (system_id,)
    ).fetchone()
    if not sys_row:
        conn.close()
        return {"system_id": system_id, "status": "rejected", "reason": "Not registered."}
    conn.close()

    state = GammaState(
        system_id=system_id,
        metrics=raw_state.get("metrics", {}),
        actions=raw_state.get("actions", []),
        priority=raw_state.get("priority", 1.0),
        metadata=raw_state.get("metadata", {}),
    )

    xform, output = _transform(state, db_path=db_path)

    # Log session
    conn = _get_conn(db_path)
    session_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    input_hash = hashlib.sha256(json.dumps(raw_state, sort_keys=True).encode()).hexdigest()[:16]
    conn.execute(
        "INSERT INTO session_log (id, system_id, session_type, input_hash, gamma_state, "
        "x_transforms, d_output, chamber_verdict, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, system_id, "transform", input_hash,
         json.dumps(asdict(state)), json.dumps(asdict(xform)),
         json.dumps(asdict(output)), json.dumps(xform.chamber_check), now)
    )
    conn.execute("UPDATE connected_system SET last_seen = ? WHERE system_id = ?", (now, system_id))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "system_id": system_id,
        "status": output.status,
        "evidence_level": output.evidence_level,
        "cost": output.cost,
        "warnings": output.warnings,
        "actions_allowed": output.actions_allowed,
        "actions_blocked": output.actions_blocked,
        "guidance": output.guidance.get("status", "unknown"),
        "timestamp": now,
    }


def get_report(system_id: str, db_path: Optional[str] = None) -> dict:
    """Get comprehensive governance report for Odysseus."""
    health = get_agent_health(system_id, db_path=db_path)
    chamber = check_chamber(db_path=db_path)
    ledger = verify_agent(system_id, db_path=db_path)
    conn = _get_conn(db_path)
    sessions = conn.execute(
        "SELECT COUNT(*) as n FROM session_log WHERE system_id = ?", (system_id,)
    ).fetchone()
    conn.close()
    return {
        "system_id": system_id,
        "ledger": ledger,
        "health": health,
        "chamber": chamber,
        "total_sessions": sessions["n"] if sessions else 0,
    }


def self_test() -> bool:
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "sb_test.db")
    try:
        for f in [db]:
            try: os.remove(f)
            except: pass
        reg = register_odysseus("TestOdysseus", trust_level="amber", chamber_depth=0)
        assert reg["system_id"] is not None
        sid = reg["system_id"]

        establish_baseline(sid, "latency", 100.0)
        set_optimal(sid, "latency", 100.0, tolerance=0.10)

        # Test healthy request
        r1 = process_request(sid, {
            "metrics": {"latency": 105.0},
            "actions": [{"type": "write_file", "source": "user", "flow": "output.txt", "loss": "disk_io", "balance": 1.0}],
        })
        assert r1["status"] in ("ok", "warning")
        assert "write_file" in r1["actions_allowed"]

        # Test anomalous request
        r2 = process_request(sid, {
            "metrics": {"latency": 500.0},
            "actions": [{"type": "delete_file", "source": "auto", "flow": "deletion", "loss": "data_loss", "balance": -5.0}],
        })
        assert r2["status"] in ("warning", "degraded", "blocked")
        assert "delete_file" in r2["actions_blocked"]

        report = get_report(sid)
        assert report["system_id"] == sid

        try: os.remove(db)
        except: pass
        print("  sandwich_bridge self-test: ALL PASS")
        return True
    except AssertionError as e:
        print(f"  sandwich_bridge self-test: FAIL - {e}")
        return False
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  sandwich_bridge self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
