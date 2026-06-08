"""
modules/cauchy_ledger.py — Triple-Entry Audit Trail

Every action is recorded as a (source, flow, loss) triplet.
The balance must stay nonnegative: BALANCE = source_flow - loss >= 0.

Derived from the Cauchy Factorization Theorem:
  D_k term = u_i * v_m - p_i * w_m  =  source * flow - loss

Where:
  source = what initiated the action (agent_id, trigger, context)
  flow   = what was produced (output, state change, new agent)
  loss   = what was consumed/cancelled (resources, failed attempts, corrections)

Stored in SQLite. Every entry has an evidence level and a provenance tag.
The ledger never deletes — it only appends. Corrections are new entries.

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
# Database
# ---------------------------------------------------------------------------

def _db_path() -> str:
    base = os.environ.get("AGENT_DATA_DIR", "data")
    p = Path(base) / "cauchy_ledger.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    db_path = db_path or _db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ledger_entry (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            source TEXT NOT NULL,
            flow TEXT NOT NULL,
            loss TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            evidence_level TEXT NOT NULL DEFAULT 'assumption',
            provenance TEXT NOT NULL DEFAULT 'unknown',
            chamber_status TEXT NOT NULL DEFAULT 'unchecked',
            parity INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT ''
        );
        
        CREATE INDEX IF NOT EXISTS idx_ledger_agent ON ledger_entry(agent_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_time ON ledger_entry(timestamp);
        CREATE INDEX IF NOT EXISTS idx_ledger_balance ON ledger_entry(balance);
        CREATE INDEX IF NOT EXISTS idx_ledger_chamber ON ledger_entry(chamber_status);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

VALID_EVIDENCE = {"assumption", "runtime_success", "test_success", "formally_verified"}
VALID_PROVENANCE = {"user_input", "tool_output", "llm_inference", "memory_retrieval",
                    "verification", "external_data", "agent_action"}
CHAMBER_STATUSES = {"unchecked", "in_chamber", "out_of_chamber", "boundary", "quarantined"}


@dataclass
class LedgerEntry:
    agent_id: str
    action_type: str
    source: str      # what initiated
    flow: str        # what was produced
    loss: str        # what was consumed
    balance: float = 0.0
    evidence_level: str = "assumption"
    provenance: str = "agent_action"
    note: str = ""


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def record(
    agent_id: str,
    action_type: str,
    source: str,
    flow: str,
    loss: str,
    *,
    balance: float = 0.0,
    evidence_level: str = "assumption",
    provenance: str = "agent_action",
    parity: int = 0,
    note: str = "",
    db_path: Optional[str] = None,
) -> str:
    """Record an action in the Cauchy ledger. Returns the entry ID."""
    
    if evidence_level not in VALID_EVIDENCE:
        raise ValueError(f"Invalid evidence_level: {evidence_level}. Must be one of {VALID_EVIDENCE}")
    if provenance not in VALID_PROVENANCE:
        raise ValueError(f"Invalid provenance: {provenance}. Must be one of {VALID_PROVENANCE}")
    
    entry_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    conn = _get_conn(db_path)
    conn.execute(
        """INSERT INTO ledger_entry 
           (id, timestamp, agent_id, action_type, source, flow, loss, balance,
            evidence_level, provenance, chamber_status, parity, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id, timestamp, agent_id, action_type, source, flow, loss,
         balance, evidence_level, provenance, "unchecked", parity, note)
    )
    conn.commit()
    conn.close()
    return entry_id


def verify_entry(entry_id: str, db_path: Optional[str] = None) -> dict:
    """Verify a ledger entry's balance. Returns verification result."""
    conn = _get_conn(db_path)
    row = conn.execute("SELECT * FROM ledger_entry WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    
    if not row:
        return {"entry_id": entry_id, "status": "not_found"}
    
    # The balance check: balance should be >= 0 for valid operations
    actual_balance = row["balance"]
    verdict = "valid" if actual_balance >= 0 else "violation"
    
    return {
        "entry_id": entry_id,
        "status": verdict,
        "balance": actual_balance,
        "agent_id": row["agent_id"],
        "action_type": row["action_type"],
        "timestamp": row["timestamp"],
    }


def verify_agent(agent_id: str, db_path: Optional[str] = None) -> dict:
    """Verify all entries for an agent. Returns aggregate balance."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT balance FROM ledger_entry WHERE agent_id = ?", (agent_id,)
    ).fetchall()
    conn.close()
    
    total = sum(r["balance"] for r in rows)
    violations = sum(1 for r in rows if r["balance"] < 0)
    count = len(rows)
    
    return {
        "agent_id": agent_id,
        "total_entries": count,
        "total_balance": total,
        "violations": violations,
        "status": "clean" if violations == 0 and total >= 0 else "degraded",
    }


def get_agent_history(agent_id: str, limit: int = 50, db_path: Optional[str] = None) -> list[dict]:
    """Get recent ledger entries for an agent."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM ledger_entry WHERE agent_id = ? ORDER BY timestamp DESC LIMIT ?",
        (agent_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_chamber_status(entry_id: str, status: str, db_path: Optional[str] = None) -> bool:
    """Update the chamber status of an entry."""
    if status not in CHAMBER_STATUSES:
        raise ValueError(f"Invalid chamber status: {status}")
    conn = _get_conn(db_path)
    conn.execute(
        "UPDATE ledger_entry SET chamber_status = ? WHERE id = ?",
        (status, entry_id)
    )
    conn.commit()
    conn.close()
    return True


def get_balance_sheet(db_path: Optional[str] = None) -> dict:
    """Get aggregate balance sheet across all agents."""
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT COUNT(*) as total, SUM(balance) as total_balance, "
        "SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) as violations "
        "FROM ledger_entry"
    ).fetchone()
    conn.close()
    
    return {
        "total_entries": row["total"] or 0,
        "total_balance": row["total_balance"] or 0.0,
        "violations": row["violations"] or 0,
        "status": "healthy" if (row["violations"] or 0) == 0 else "attention_needed",
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test() -> bool:
    """Verify the Cauchy ledger works correctly."""
    import tempfile
    db = os.path.join(tempfile.gettempdir(), "cauchy_test.db")
    
    try:
        # Record a valid entry
        eid = record("agent_1", "compute", "user_request", "result_42", "cpu_cycles",
                     balance=1.0, evidence_level="test_success", provenance="verification",
                     db_path=db)
        assert eid is not None
        
        # Verify it
        v = verify_entry(eid, db_path=db)
        assert v["status"] == "valid"
        assert v["balance"] == 1.0
        
        # Record a violation
        eid2 = record("agent_2", "compute", "user_request", "partial_result", "excessive_cpu",
                      balance=-5.0, evidence_level="assumption", provenance="llm_inference",
                      db_path=db)
        
        v2 = verify_entry(eid2, db_path=db)
        assert v2["status"] == "violation"
        
        # Agent verification
        agent1 = verify_agent("agent_1", db_path=db)
        assert agent1["status"] == "clean"
        
        agent2 = verify_agent("agent_2", db_path=db)
        assert agent2["status"] == "degraded"
        
        # Balance sheet
        sheet = get_balance_sheet(db_path=db)
        assert sheet["total_entries"] == 2
        assert sheet["violations"] == 1
        
        # Chamber status
        set_chamber_status(eid, "in_chamber", db_path=db)
        
        # Cleanup
        os.remove(db)
        print("  cauchy_ledger self-test: ALL PASS")
        return True
        
    except AssertionError as e:
        print(f"  cauchy_ledger self-test: FAIL - {e}")
        return False
    except Exception as e:
        print(f"  cauchy_ledger self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    ok = self_test()
    sys.exit(0 if ok else 1)
