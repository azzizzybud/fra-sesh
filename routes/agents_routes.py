"""
routes/agents_routes.py — FRA Agents Dashboard API

Surfaces the real Feather Research Agent processes (from FRA_DIR) so they
are visible and controllable from the FRA Sesh UI:

  GET  /api/fra/agents                      — list agents with live status
  POST /api/fra/agents/{agent_id}/run       — start an action (one-shot or watch)
  POST /api/fra/agents/{agent_id}/stop      — stop the agent's running process
  GET  /api/fra/agents/{agent_id}/output    — tail of the current/last run log

Agents run as subprocesses of FRA_DIR's CLI entry points. One process per
agent at a time. Output streams to data/fra_agents/logs/<agent>-<ts>.log so
it survives a UI reload. The catalog can be extended without code changes by
dropping extra entries into data/fra_agents/catalog.json (same shape as
_DEFAULT_CATALOG entries).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("fra_agents.routes")

FRA_DIR = os.environ.get(
    "FRA_DIR",
    r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent",
)
def _resolve_fra_python() -> str:
    """Prefer FRA's own venv so agent runs get FRA's dependencies."""
    explicit = os.environ.get("FRA_PYTHON")
    if explicit:
        return explicit
    venv_python = os.path.join(FRA_DIR, ".venv", "Scripts", "python.exe")
    if os.path.isfile(venv_python):
        return venv_python
    return sys.executable


FRA_PYTHON = _resolve_fra_python()

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "fra_agents"
_LOG_DIR = _DATA_DIR / "logs"
_CATALOG_FILE = _DATA_DIR / "catalog.json"

# ---------------------------------------------------------------------------
# Agent catalog
# ---------------------------------------------------------------------------
# kind: "oneshot" — runs to completion, status returns to idle on exit
#       "watch"   — long-running loop, runs until stopped
_DEFAULT_CATALOG = [
    {
        "id": "research_supervisor",
        "name": "Research Supervisor",
        "description": "Core FRA orchestrator — environment check, log scan, lane classification, dashboard write-back to Feather Core.",
        "category": "Research",
        "actions": [
            {"id": "tick", "label": "Run Tick", "kind": "oneshot",
             "args": ["feather_research_agent.py", "tick"], "timeout": 600},
            {"id": "stats", "label": "Stats", "kind": "oneshot",
             "args": ["feather_research_agent.py", "stats"], "timeout": 120},
            {"id": "node", "label": "Node Loop", "kind": "watch",
             "args": ["feather_research_agent.py", "node-start"]},
        ],
    },
    {
        "id": "math_agent",
        "name": "Math Agent",
        "description": "Autonomous mathematical exploration (SBT / RH programme), DeepSeek-assisted probing with findings stored to the intelligence DB.",
        "category": "Research",
        "actions": [
            {"id": "explore", "label": "Explore", "kind": "oneshot",
             "args": ["feather_research_agent.py", "math-explore"], "timeout": 1800},
        ],
    },
    {
        "id": "jt_programme",
        "name": "Jensen–Turán Scanner",
        "description": "Jensen–Turán RH research programme — runs scans for violations and reports programme status.",
        "category": "Research",
        "actions": [
            {"id": "status", "label": "Status", "kind": "oneshot",
             "args": ["feather_research_agent.py", "jt", "--action", "status"], "timeout": 120},
            {"id": "scan", "label": "Run Scan", "kind": "oneshot",
             "args": ["feather_research_agent.py", "jt", "--action", "scan"], "timeout": 1800},
        ],
    },
    {
        "id": "three_agent_loop",
        "name": "3-Agent Research Loop",
        "description": "Math Checker → Simple Explainer → Next-Prompt Writer over the latest FRA research output; writes NEXT_FRA_PROMPT.txt.",
        "category": "Research",
        "actions": [
            {"id": "loop", "label": "Run Loop", "kind": "oneshot",
             "args": ["fra_3agent_loop.py", "--last"], "timeout": 900},
        ],
    },
    {
        "id": "content_agent",
        "name": "Content Generator",
        "description": "Generates content packages — short-form scripts, captions, hashtags, LinkedIn posts — from the product knowledge base.",
        "category": "Content",
        "actions": [
            {"id": "generate", "label": "Generate", "kind": "oneshot",
             "args": ["feather_research_agent.py", "content"], "timeout": 600},
        ],
    },
    {
        "id": "nachweis_collector",
        "name": "Nachweis Prospect Collector",
        "description": "Collects cold-email prospects into the Nachweis pipeline.",
        "category": "Marketing",
        "actions": [
            {"id": "run", "label": "Run Once", "kind": "oneshot",
             "args": ["feather_research_agent.py", "nachweis-collect", "--run"], "timeout": 900},
            {"id": "stats", "label": "Stats", "kind": "oneshot",
             "args": ["feather_research_agent.py", "nachweis-collect", "--stats"], "timeout": 120},
            {"id": "watch", "label": "Continuous", "kind": "watch",
             "args": ["feather_research_agent.py", "nachweis-collect", "--start"]},
        ],
    },
    {
        "id": "nachweis_copywriter",
        "name": "Nachweis Copywriter",
        "description": "Drafts cold emails for collected prospects (generate only — nothing is sent).",
        "category": "Marketing",
        "actions": [
            {"id": "generate", "label": "Generate", "kind": "oneshot",
             "args": ["feather_research_agent.py", "nachweis-copy", "--generate"], "timeout": 900},
        ],
    },
    {
        "id": "nachweis_sender",
        "name": "Nachweis Sender",
        "description": "Sends approved emails via Resend and reports pipeline status.",
        "category": "Marketing",
        "actions": [
            {"id": "status", "label": "Pipeline Status", "kind": "oneshot",
             "args": ["feather_research_agent.py", "nachweis-status"], "timeout": 120},
            {"id": "send", "label": "Send Batch (10)", "kind": "oneshot",
             "args": ["feather_research_agent.py", "nachweis-send", "--batch", "10"], "timeout": 900},
        ],
    },
    {
        "id": "telegram_bot",
        "name": "Telegram Bridge",
        "description": "Telegram doorway — receives commands and sends FRA reports until stopped.",
        "category": "Doorways",
        "actions": [
            {"id": "start", "label": "Start Bot", "kind": "watch",
             "args": ["feather_research_agent.py", "telegram-start"]},
        ],
    },
    {
        "id": "self_test",
        "name": "Module Self-Tests",
        "description": "Runs every FRA module's --self-test for a full health pass.",
        "category": "Maintenance",
        "actions": [
            {"id": "test", "label": "Run Self-Tests", "kind": "oneshot",
             "args": ["feather_research_agent.py", "self-test"], "timeout": 900},
        ],
    },
]


def _load_catalog() -> list[dict]:
    catalog = [dict(a) for a in _DEFAULT_CATALOG]
    if _CATALOG_FILE.exists():
        try:
            extra = json.loads(_CATALOG_FILE.read_text(encoding="utf-8"))
            known = {a["id"] for a in catalog}
            for entry in extra:
                if isinstance(entry, dict) and entry.get("id") and entry["id"] not in known:
                    catalog.append(entry)
        except Exception as e:
            logger.warning(f"Failed to read {_CATALOG_FILE}: {e}")
    return catalog


# ---------------------------------------------------------------------------
# Process manager — one live process per agent
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()
_PROCS: dict[str, dict] = {}      # agent_id -> {proc, action, kind, started_at, log_path}
_LAST_RUNS: dict[str, dict] = {}  # agent_id -> {action, started_at, finished_at, returncode, log_path}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reap(agent_id: str) -> None:
    """If the agent's process has exited, move it from _PROCS to _LAST_RUNS."""
    entry = _PROCS.get(agent_id)
    if not entry:
        return
    rc = entry["proc"].poll()
    if rc is None:
        return
    try:
        entry["log_file"].close()
    except Exception:
        pass
    _PROCS.pop(agent_id, None)
    _LAST_RUNS[agent_id] = {
        "action": entry["action"],
        "kind": entry["kind"],
        "started_at": entry["started_at"],
        "finished_at": _now(),
        "returncode": rc,
        "log_path": entry["log_path"],
    }


def _spawn(agent: dict, action: dict) -> dict:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = _LOG_DIR / f"{agent['id']}-{ts}.log"
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    log_file.write(
        f"# {agent['name']} — {action['label']}\n"
        f"# {FRA_PYTHON} {' '.join(action['args'])}\n"
        f"# cwd: {FRA_DIR}\n# started: {_now()}\n\n"
    )
    log_file.flush()
    env = os.environ.copy()
    env["PYTHONPATH"] = FRA_DIR + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [FRA_PYTHON] + list(action["args"]),
        cwd=FRA_DIR,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    entry = {
        "proc": proc,
        "log_file": log_file,
        "log_path": str(log_path),
        "action": action["id"],
        "action_label": action["label"],
        "kind": action["kind"],
        "started_at": _now(),
    }
    _PROCS[agent["id"]] = entry
    logger.info(f"FRA agent started: {agent['id']}/{action['id']} pid={proc.pid}")
    return entry


def _agent_status(agent_id: str) -> dict:
    _reap(agent_id)
    entry = _PROCS.get(agent_id)
    if entry:
        return {
            "state": "running",
            "action": entry["action"],
            "action_label": entry["action_label"],
            "kind": entry["kind"],
            "pid": entry["proc"].pid,
            "started_at": entry["started_at"],
        }
    last = _LAST_RUNS.get(agent_id)
    return {"state": "idle", "last_run": last}


def _tail(path: str, max_bytes: int = 16384) -> str:
    try:
        size = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # drop partial line
            return f.read()
    except OSError as e:
        return f"(no output available: {e})"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/fra/agents", tags=["fra-agents"])


class RunRequest(BaseModel):
    action: str
    extra_args: list[str] = []


def _find(catalog: list[dict], agent_id: str) -> dict:
    for a in catalog:
        if a["id"] == agent_id:
            return a
    raise HTTPException(404, f"Unknown agent: {agent_id}")


@router.get("")
async def list_agents():
    """All agents with live status. Frontend polls this while the panel is open."""
    catalog = _load_catalog()
    with _LOCK:
        agents = []
        for a in catalog:
            agents.append({
                "id": a["id"],
                "name": a["name"],
                "description": a["description"],
                "category": a.get("category", "Other"),
                "actions": [
                    {"id": act["id"], "label": act["label"], "kind": act["kind"]}
                    for act in a.get("actions", [])
                ],
                "status": _agent_status(a["id"]),
            })
    return {
        "fra_dir": FRA_DIR,
        "fra_dir_exists": os.path.isdir(FRA_DIR),
        "agents": agents,
    }


@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, body: RunRequest):
    """Start an agent action (one-shot or watch). One process per agent."""
    catalog = _load_catalog()
    agent = _find(catalog, agent_id)
    action = next((x for x in agent.get("actions", []) if x["id"] == body.action), None)
    if not action:
        raise HTTPException(404, f"Unknown action '{body.action}' for agent '{agent_id}'")
    if not os.path.isdir(FRA_DIR):
        raise HTTPException(500, f"FRA_DIR not found: {FRA_DIR}")
    script = os.path.join(FRA_DIR, action["args"][0])
    if not os.path.isfile(script):
        raise HTTPException(500, f"Agent entry point missing: {script}")

    with _LOCK:
        _reap(agent_id)
        if agent_id in _PROCS:
            raise HTTPException(409, f"{agent['name']} is already running")
        action = dict(action)
        action["args"] = list(action["args"]) + [str(x) for x in body.extra_args]
        try:
            entry = _spawn(agent, action)
        except OSError as e:
            raise HTTPException(500, f"Failed to start agent: {e}")

    return {
        "ok": True,
        "agent_id": agent_id,
        "action": action["id"],
        "kind": action["kind"],
        "pid": entry["proc"].pid,
        "started_at": entry["started_at"],
    }


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Terminate the agent's running process."""
    with _LOCK:
        _reap(agent_id)
        entry = _PROCS.get(agent_id)
        if not entry:
            raise HTTPException(409, f"Agent '{agent_id}' is not running")
        proc = entry["proc"]
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        except OSError as e:
            raise HTTPException(500, f"Failed to stop process: {e}")
        _reap(agent_id)
    return {"ok": True, "agent_id": agent_id, "stopped_at": _now()}


@router.get("/{agent_id}/output")
async def agent_output(agent_id: str):
    """Tail of the current run's log, or the last finished run."""
    with _LOCK:
        _reap(agent_id)
        entry = _PROCS.get(agent_id)
        if entry:
            try:
                entry["log_file"].flush()
            except Exception:
                pass
            return {
                "agent_id": agent_id,
                "state": "running",
                "log_path": entry["log_path"],
                "output": _tail(entry["log_path"]),
            }
        last = _LAST_RUNS.get(agent_id)
    if not last:
        return {"agent_id": agent_id, "state": "idle", "output": "(no runs yet this session)"}
    return {
        "agent_id": agent_id,
        "state": "idle",
        "returncode": last["returncode"],
        "finished_at": last["finished_at"],
        "log_path": last["log_path"],
        "output": _tail(last["log_path"]),
    }
