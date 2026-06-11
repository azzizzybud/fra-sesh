"""
fra_governance/startup.py — Auto-register FRA Sesh on Odysseus startup

Called during app.py lifespan startup. Registers the FRA session with
governance if not already registered, establishes baselines, and
prepares the sandwich bridge for operation.

This is the glue between Odysseus's FastAPI lifecycle and the
Vine/SBT mathematical governance layer.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from fra_governance.sandwich_bridge import register_fra_sesh
from fra_governance.baseline_tracker import establish_baseline
from fra_governance.cost_function import set_optimal

logger = logging.getLogger("fra_governance.startup")

FRA_SYSTEM_ID_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "fra_system_id.json"
)


def ensure_fra_registered() -> dict:
    """Register FRA Sesh with governance if not already registered.

    Returns dict with system_id, newly_registered bool, and status.
    Idempotent — safe to call on every startup.
    """
    already_registered = False
    if os.path.exists(FRA_SYSTEM_ID_FILE):
        try:
            with open(FRA_SYSTEM_ID_FILE, "r") as f:
                existing = json.load(f)
            if existing.get("system_id"):
                already_registered = True
        except Exception:
            pass

    if not already_registered:
        reg = register_fra_sesh(
            system_name="FRA Sesh",
            trust_level="amber",
            chamber_depth=0,
        )
        sid = reg["system_id"]

        # Establish baseline metrics for the FRA session
        baselines = {
            "latency": {"value": 200.0, "tolerance": 0.30},
            "api_calls": {"value": 10.0, "tolerance": 0.50},
            "tool_calls": {"value": 5.0, "tolerance": 0.50},
            "error_rate": {"value": 0.0, "tolerance": 0.10},
            "response_size": {"value": 4096.0, "tolerance": 0.50},
            "session_rounds": {"value": 3.0, "tolerance": 0.60},
            "memory_recall": {"value": 1.0, "tolerance": 0.20},
            "bash_ops": {"value": 2.0, "tolerance": 0.70},
        }

        for metric, cfg in baselines.items():
            establish_baseline(sid, metric, cfg["value"])
            set_optimal(sid, metric, cfg["value"], tolerance=cfg["tolerance"])

        os.makedirs(os.path.dirname(FRA_SYSTEM_ID_FILE), exist_ok=True)
        with open(FRA_SYSTEM_ID_FILE, "w") as f:
            json.dump({
                "system_id": sid,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "system_name": "FRA Sesh",
                "trust_level": "amber",
            }, f)

        logger.info(f"FRA governance: registered new system {sid}")
        return {"system_id": sid, "newly_registered": True, "status": "active"}
    else:
        with open(FRA_SYSTEM_ID_FILE, "r") as f:
            existing = json.load(f)
        sid = existing.get("system_id")
        logger.info(f"FRA governance: system {sid} already registered")
        return {"system_id": sid, "newly_registered": False, "status": "active"}


def get_system_id() -> str | None:
    """Get the current FRA system ID without triggering registration."""
    try:
        if os.path.exists(FRA_SYSTEM_ID_FILE):
            with open(FRA_SYSTEM_ID_FILE, "r") as f:
                data = json.load(f)
            return data.get("system_id")
    except Exception:
        pass
    return None
