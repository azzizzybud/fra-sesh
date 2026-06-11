"""
routes/fra_routes.py — FRA Governance API Endpoints

Provides the governance dashboard and control surface for FRA:
  GET  /api/fra/status        — Full governance report
  GET  /api/fra/ledger        — Cauchy ledger audit trail
  GET  /api/fra/chamber       — Chamber priority order status
  GET  /api/fra/health        — Agent health across all modules
  POST /api/fra/register      — Register a new governed system
  POST /api/fra/report        — Process a state through governance
  GET  /api/fra/sandwich/test — Run self-tests
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("fra_governance.routes")

FRA_SYSTEM_ID_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "fra_system_id.json"
)


def _get_data_dir() -> str:
    base = os.environ.get("ODYSSEUS_DATA_DIR", os.environ.get("AGENT_DATA_DIR", "data"))
    return base


class RegisterRequest(BaseModel):
    system_name: str = "FRA Sesh"
    trust_level: str = "amber"
    chamber_depth: int = 0


class ProcessRequest(BaseModel):
    system_id: str
    metrics: dict = {}
    actions: list = []
    metadata: dict = {}


router = APIRouter(prefix="/api/fra", tags=["fra-governance"])


@router.get("/status")
async def fra_status():
    """Full FRA governance status report."""
    from fra_governance import get_report as sb_report
    from fra_governance.cauchy_ledger import get_balance_sheet
    from fra_governance.chamber_monitor import get_chamber_status
    from fra_governance.baseline_tracker import get_system_health

    system_id = _load_system_id()
    if not system_id:
        return {"status": "unregistered", "message": "No FRA system registered. POST /api/fra/register first."}

    report = sb_report(system_id)
    balance = get_balance_sheet(system_id)
    chamber = get_chamber_status()
    system_health = get_system_health()

    return {
        "status": "active",
        "system_id": system_id,
        "governance_report": report,
        "balance_sheet": balance,
        "chamber": chamber,
        "system_health": system_health,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ledger")
async def fra_ledger(limit: int = 50):
    """Recent Cauchy ledger entries (audit trail)."""
    from fra_governance.cauchy_ledger import get_agent_history

    system_id = _load_system_id()
    if not system_id:
        raise HTTPException(status_code=404, detail="No FRA system registered.")

    history = get_agent_history(system_id, limit=limit)
    return {"system_id": system_id, "entries": history, "count": len(history)}


@router.get("/chamber")
async def fra_chamber():
    """Chamber priority order and parity status."""
    from fra_governance.chamber_monitor import get_chamber_status, check_parity

    system_id = _load_system_id()
    chamber = get_chamber_status()
    parity = check_parity(system_id) if system_id else {"status": "no_system"}

    return {"chamber": chamber, "parity": parity}


@router.get("/health")
async def fra_health():
    """Agent health across all governance modules."""
    from fra_governance.baseline_tracker import get_agent_health, get_system_health
    from fra_governance.bezoutian_verifier import get_structural_health
    from fra_governance.repair_pipeline import get_health_report

    system_id = _load_system_id()
    if not system_id:
        raise HTTPException(status_code=404, detail="No FRA system registered.")

    return {
        "system_id": system_id,
        "baseline_health": get_agent_health(system_id),
        "system_health": get_system_health(),
        "structural_health": get_structural_health(system_id),
        "repair_health": get_health_report(system_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/register")
async def fra_register(body: RegisterRequest):
    """Register a new system (or re-register FRA Sesh) with governance."""
    from fra_governance.sandwich_bridge import register_fra_sesh
    from fra_governance.baseline_tracker import establish_baseline
    from fra_governance.cost_function import set_optimal

    reg = register_fra_sesh(
        system_name=body.system_name,
        trust_level=body.trust_level,
        chamber_depth=body.chamber_depth,
    )

    sid = reg["system_id"]

    # Establish initial baselines
    for metric, value in [
        ("latency", 200.0),
        ("api_calls", 10.0),
        ("tool_calls", 5.0),
        ("error_rate", 0.0),
        ("response_size", 4096.0),
    ]:
        establish_baseline(sid, metric, value)
        set_optimal(sid, metric, value, tolerance=0.30)

    _save_system_id(sid, reg)

    return {
        "status": "registered",
        "system_id": sid,
        "system_name": body.system_name,
        "trust_level": body.trust_level,
        "auth_token": reg.get("auth_token"),
    }


@router.post("/report")
async def fra_process(body: ProcessRequest):
    """Process a state through the sandwich bridge governance."""
    from fra_governance.sandwich_bridge import process_request

    result = process_request(body.system_id, body.dict())
    return result


@router.get("/sandwich/test")
async def fra_sandwich_test():
    """Run all governance module self-tests."""
    from fra_governance import run_all_self_tests

    results = run_all_self_tests()
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    return {
        "results": {k: "PASS" if v else "FAIL" for k, v in results.items()},
        "passed": passed,
        "total": total,
        "all_pass": passed == total,
    }


@router.get("/dashboard")
async def fra_dashboard():
    """Consolidated governance dashboard for the UI."""
    system_id = _load_system_id()
    if not system_id:
        return {
            "status": "unregistered",
            "modules": {},
            "recent_sessions": 0,
            "total_entries": 0,
            "health_summary": "Not registered",
        }

    from fra_governance import get_report as sb_report
    from fra_governance.cauchy_ledger import verify_agent

    report = sb_report(system_id)
    ledger_verification = verify_agent(system_id)

    return {
        "status": "active",
        "system_id": system_id,
        "ledger": ledger_verification,
        "health": report.get("health", {}),
        "chamber": report.get("chamber", {}),
        "total_sessions": report.get("total_sessions", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Memory Bridge Endpoints ───────────────────────────────────────────────────

class MemoryWrite(BaseModel):
    title: str
    summary: str
    tags: list[str] = []
    details: dict = {}
    importance: int = 4


class SessionSummaryWrite(BaseModel):
    session_label: str
    findings: str
    verdict: str = ""
    next_action: str = ""


class ResearchStateWrite(BaseModel):
    proved_results: list[str] = []
    open_problems: list[str] = []
    blocked_routes: list[str] = []
    active_route: str = "unknown"
    session_count: int = 0


@router.get("/memory/recent")
async def fra_memory_recent(limit: int = 20, category: str = None, source: str = "fra-research-agent"):
    """Read recent FRA memories from Open Brain."""
    from fra_governance.fra_memory import read_recent_memories
    memories = read_recent_memories(limit=limit, category=category or None, source=source)
    return {"count": len(memories), "memories": memories}


@router.get("/memory/search")
async def fra_memory_search(q: str, limit: int = 10):
    """Search FRA memories by text."""
    from fra_governance.fra_memory import search_memories
    results = search_memories(q, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/memory/tag/{tag}")
async def fra_memory_by_tag(tag: str, limit: int = 20):
    """Get memories by tag."""
    from fra_governance.fra_memory import read_memories_by_tag
    memories = read_memories_by_tag(tag, limit=limit)
    return {"tag": tag, "count": len(memories), "memories": memories}


@router.post("/memory/write")
async def fra_memory_write(body: MemoryWrite):
    """Write a research memory to Open Brain."""
    from fra_governance.fra_memory import write_research_memory
    result = write_research_memory(
        title=body.title,
        summary=body.summary,
        tags=body.tags,
        details=body.details,
        importance=body.importance,
    )
    if result:
        return {"status": "written", "memory_id": result.get("id")}
    return {"status": "skipped", "reason": "Supabase unavailable"}


@router.post("/memory/session")
async def fra_memory_session(body: SessionSummaryWrite):
    """Save a session summary to Open Brain."""
    from fra_governance.fra_memory import save_session_summary
    system_id = _load_system_id() or "unknown"
    result = save_session_summary(
        system_id=system_id,
        session_label=body.session_label,
        findings=body.findings,
        verdict=body.verdict,
        next_action=body.next_action,
    )
    if result:
        return {"status": "saved", "memory_id": result.get("id")}
    return {"status": "skipped", "reason": "Supabase unavailable"}


@router.post("/memory/research-state")
async def fra_memory_research_state(body: ResearchStateWrite):
    """Save complete research state snapshot."""
    from fra_governance.fra_memory import save_research_state
    system_id = _load_system_id() or "unknown"
    result = save_research_state(
        system_id=system_id,
        proved_results=body.proved_results,
        open_problems=body.open_problems,
        blocked_routes=body.blocked_routes,
        active_route=body.active_route,
        session_count=body.session_count,
    )
    if result:
        return {"status": "saved", "memory_id": result.get("id")}
    return {"status": "skipped", "reason": "Supabase unavailable"}


@router.get("/memory/context")
async def fra_memory_context():
    """Assemble full context for a new FRA session (BRAIN.md + recent memories + governance)."""
    from fra_governance.fra_memory import assemble_session_context, read_brain_md

    system_id = _load_system_id()
    if not system_id:
        return {"status": "unregistered", "message": "Register FRA first at POST /api/fra/register"}

    context = assemble_session_context(system_id)
    brain = read_brain_md()
    context["brain_summary"] = brain[:500] if brain else "BRAIN.md not found"

    return {"status": "ok", "context": context}


@router.get("/memory/brain")
async def fra_memory_brain():
    """Return the full BRAIN.md content."""
    from fra_governance.fra_memory import read_brain_md
    brain = read_brain_md()
    if brain:
        return {"status": "ok", "content": brain}
    return {"status": "not_found", "message": "BRAIN.md not found"}


@router.post("/memory/theorem")
async def fra_memory_theorem(
    name: str = "",
    statement: str = "",
    status: str = "open",
    proof_sketch: str = "",
    evidence_level: str = "assumption",
):
    """Record a theorem result to Open Brain."""
    from fra_governance.fra_memory import record_theorem
    result = record_theorem(
        name=name,
        statement=statement,
        status=status,
        proof_sketch=proof_sketch,
        evidence_level=evidence_level,
    )
    if result:
        return {"status": "recorded", "memory_id": result.get("id")}
    return {"status": "skipped", "reason": "Supabase unavailable"}


# ── Parallel Execution Endpoints ──────────────────────────────────────────────

class ParallelLaunchRequest(BaseModel):
    tracks: list[dict] = []  # Custom track specs, or empty for standard 4-track
    max_concurrent: int = 4
    python_exe: str = r"C:\Windows\py.exe"
    rh_dir: str = r"C:\Users\info\OneDrive\Desktop\RH"


class CustomTrackSpec(BaseModel):
    name: str
    script: str
    type: str = "numerical"
    timeout: int = 300
    description: str = ""


@router.post("/parallel/launch")
async def fra_parallel_launch(body: ParallelLaunchRequest):
    """Launch FRA parallel research tracks concurrently.

    With no custom tracks, launches the standard 4-track JT programme:
      Track 1: Precision recheck (dps=120)
      Track 2: JT-R1 boundary scan
      Track 3: d=1 base case (Hamburger verification)
      Track 4: Cauchy-Schwarz / Gram matrix
    """
    from fra_governance.parallel_engine import (
        execute_parallel_tracks, build_standard_fra_tracks,
        build_custom_tracks, merge_findings,
    )

    system_id = _load_system_id()

    if body.tracks:
        tracks = build_custom_tracks(
            script_dir=body.rh_dir,
            scripts=body.tracks,
            python_exe=body.python_exe,
        )
    else:
        tracks = build_standard_fra_tracks(
            rh_dir=body.rh_dir,
            python_exe=body.python_exe,
        )

    if not tracks:
        return {"status": "error", "message": "No valid tracks found. Check script paths."}

    result = await execute_parallel_tracks(
        tracks=tracks,
        max_concurrent=body.max_concurrent,
        system_id=system_id,
    )

    output_dir = body.rh_dir or r"C:\Users\info\OneDrive\Desktop\RH"
    report_path = os.path.join(output_dir, f"parallel_report_{result.session_id}.md")
    merge_findings(result, report_path)

    return {
        "status": "complete",
        "session_id": result.session_id,
        "total_duration": result.total_duration,
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "timeout_count": result.timeout_count,
        "report_path": report_path,
        "track_results": [
            {
                "track_id": t.track_id,
                "name": t.name,
                "status": t.status,
                "duration": t.duration_seconds,
                "evidence_level": t.evidence_level,
                "error": t.error[:200] if t.error else None,
            }
            for t in result.tracks
        ],
    }


@router.get("/parallel/status")
async def fra_parallel_status():
    """Check which standard FRA track scripts are available."""
    from fra_governance.parallel_engine import build_standard_fra_tracks

    tracks = build_standard_fra_tracks()
    return {
        "tracks_available": len(tracks),
        "tracks": [
            {
                "track_id": t.track_id,
                "name": t.name,
                "type": t.track_type,
                "script_exists": bool(t.script_path and os.path.exists(t.script_path)),
                "script_path": t.script_path,
            }
            for t in tracks
        ],
    }


# ── Universal Research Endpoints ──────────────────────────────────────────────

@router.get("/universal/systems")
async def fra_universal_systems():
    """List all 10 systems in the Universal Balance Programme."""
    from fra_governance.universal_research import get_all_systems
    systems = get_all_systems()
    return {
        "count": len(systems),
        "systems": [
            {
                "id": s.sys_id,
                "name": s.name,
                "domain": s.domain,
                "classification": s.classification,
                "is_active": s.is_active,
                "description": s.description[:200],
            }
            for s in systems
        ],
    }


@router.get("/universal/system/{sys_id}")
async def fra_universal_system(sys_id: str):
    """Get detailed info on one research system."""
    from fra_governance.universal_research import get_system, build_system_prompt
    system = get_system(sys_id)
    if not system:
        raise HTTPException(status_code=404, detail=f"System {sys_id} not found")

    prompt = build_system_prompt(sys_id)
    return {
        "id": system.sys_id,
        "name": system.name,
        "domain": system.domain,
        "classification": system.classification,
        "description": system.description,
        "gap": system.gap,
        "epsilon": system.epsilon,
        "reservoirs": system.reservoirs,
        "natural_reservoirs": system.natural_reservoirs,
        "note": system.note,
        "research_prompt": prompt,
    }


@router.get("/universal/dashboard")
async def fra_universal_dashboard():
    """Full universal research dashboard across all systems."""
    from fra_governance.universal_research import build_universal_dashboard
    return build_universal_dashboard()


@router.get("/universal/priority")
async def fra_universal_priority():
    """Systems ordered by research priority."""
    from fra_governance.universal_research import get_research_priority
    return {"priorities": get_research_priority()}


@router.get("/universal/theorems")
async def fra_universal_theorems():
    """All discovered Feather theorems."""
    from fra_governance.universal_research import get_theorems, get_route_labels
    return {
        "theorems": get_theorems(),
        "route_labels": get_route_labels(),
    }


class RecordFindingRequest(BaseModel):
    sys_id: str
    finding_type: str = "open"  # "proved", "open", "blocked"
    description: str
    evidence_level: str = "assumption"


@router.post("/universal/record")
async def fra_universal_record(body: RecordFindingRequest):
    """Record a research finding for any system."""
    from fra_governance.universal_research import record_system_session
    record_system_session(
        sys_id=body.sys_id,
        finding_type=body.finding_type,
        description=body.description,
        evidence_level=body.evidence_level,
    )
    return {"status": "recorded", "sys_id": body.sys_id, "type": body.finding_type}


# ── Output Pipeline Endpoints (#5 Panel, #6 Content, #7 Humanizer) ────────────

class OutputProcessRequest(BaseModel):
    title: str
    raw_findings: str
    domain: str = "research"
    humanize_intensity: str = "medium"
    content_format: str = "short_form"


@router.post("/output/process")
async def fra_output_process(body: OutputProcessRequest):
    """Full pipeline: Panel evaluation + Humanizer + Content brief."""
    from fra_governance.fra_output import process_fra_output
    system_id = _load_system_id()
    result = process_fra_output(
        title=body.title,
        raw_findings=body.raw_findings,
        domain=body.domain,
        humanize_intensity=body.humanize_intensity,
        content_format=body.content_format,
        system_id=system_id,
    )
    return result


class EvaluateRequest(BaseModel):
    title: str
    content: str
    domain: str = "research"


@router.post("/output/panel")
async def fra_output_panel(body: EvaluateRequest):
    """Run Feather Panel evaluation only."""
    from fra_governance.fra_output import evaluate_with_panel
    panel = evaluate_with_panel(body.title, body.content, body.domain)
    return {
        "title": body.title,
        "approved": panel.publish_approved,
        "maat_score": round(panel.avg_maat_score, 1),
        "has_drift": panel.has_drift,
        "verdict": panel.agreed_recommendation,
        "revision_needed": panel.revision_needed,
        "personas": {
            "partner": {"verdict": panel.partner.verdict, "drift": panel.partner.drift_flag, "maat": panel.partner.maat_score},
            "advisor": {"verdict": panel.advisor.verdict, "drift": panel.advisor.drift_flag, "maat": panel.advisor.maat_score},
            "colleague": {"verdict": panel.colleague.verdict, "drift": panel.colleague.drift_flag, "maat": panel.colleague.maat_score},
            "friend": {"verdict": panel.friend.verdict, "drift": panel.friend.drift_flag, "maat": panel.friend.maat_score},
        },
    }


class HumanizeRequest(BaseModel):
    text: str
    intensity: str = "medium"


@router.post("/output/humanize")
async def fra_output_humanize(body: HumanizeRequest):
    """Run Humanizer on text."""
    from fra_governance.fra_output import humanize_text, humanize_score
    result = humanize_text(body.text, body.intensity)
    score = humanize_score(body.text)
    return {
        "humanized": result,
        "original_score": score,
        "new_score": humanize_score(result),
        "intensity": body.intensity,
    }


class ContentBriefRequest(BaseModel):
    title: str
    findings: str
    format: str = "short_form"


@router.post("/output/content-brief")
async def fra_output_content_brief(body: ContentBriefRequest):
    """Generate a Content Studio production brief from FRA findings."""
    from fra_governance.fra_output import research_to_content_brief, generate_video_asset_specs
    brief = research_to_content_brief(body.title, body.findings, body.format)
    specs = generate_video_asset_specs(brief)
    return {
        "brief": {
            "title": brief.title,
            "angle": brief.angle,
            "format": brief.format,
            "hook_type": brief.hook_type,
            "target_runtime": brief.target_runtime_seconds,
            "target_words": brief.target_word_count,
            "sections": brief.script_sections,
        },
        "asset_specs": specs,
    }


def _load_system_id() -> str | None:
    try:
        if os.path.exists(FRA_SYSTEM_ID_FILE):
            with open(FRA_SYSTEM_ID_FILE, "r") as f:
                data = json.load(f)
            return data.get("system_id")
    except Exception:
        pass
    return None


def _save_system_id(system_id: str, reg: dict):
    os.makedirs(os.path.dirname(FRA_SYSTEM_ID_FILE), exist_ok=True)
    with open(FRA_SYSTEM_ID_FILE, "w") as f:
        json.dump({"system_id": system_id, "registered_at": datetime.now(timezone.utc).isoformat(), "system_name": reg.get("system_name", "FRA Sesh")}, f)
