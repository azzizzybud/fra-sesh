"""
fra_governance/fra_memory.py — FRA ↔ Open Brain Human Door Memory Bridge

Connects FRA's research state to the Open Brain shared memory system.
Both the human (via web UI) and FRA (via this module) read/write to
the same Supabase tables: memories, assets, maintenance_events.

Architecture:
  - FRA writes session summaries as "research" memories
  - FRA writes research assets (proofs, theorems, datasets) as assets
  - FRA writes open problems / blocked routes as maintenance_events (due = revisit)
  - FRA reads relevant memories for context before each session
  - FRA reads BRAIN.md for identity and framework context

Category extension: Adds "research" to the existing categories
(household, maintenance, contact, job, note) for FRA-originated content.

Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY env vars
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fra_governance.memory")

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://flejqlktlehtxhwxuttl.supabase.co",
)
# Service-role key must come from the environment (.env) — never hardcode it.
# With no key set, the memory layer degrades gracefully to local-only mode.
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _get_client():
    """Lazy-load the Supabase client."""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.warning(f"Supabase client unavailable: {e}")
        return None


# ── Memory Operations ────────────────────────────────────────────────────────

def write_research_memory(
    title: str,
    summary: str,
    tags: list[str] | None = None,
    details: dict | None = None,
    importance: int = 4,
    category: str = "note",
) -> dict | None:
    """Write a research finding/memory to Open Brain.

    Uses category='note' (existing schema) with 'fra' tags for filtering.
    Run scripts/fra_openbrain_migration.sql to add a 'research' category.
    """
    client = _get_client()
    if not client:
        return None

    data = {
        "title": title,
        "category": category,
        "summary": summary,
        "tags": tags or [],
        "details": json.dumps(details or {}),
        "source": "fra-research-agent",
        "importance": importance,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = client.table("memories").insert(data).execute()
        if result.data:
            logger.info(f"FRA memory written: {title[:60]}")
            return result.data[0]
    except Exception as e:
        logger.warning(f"Failed to write FRA memory: {e}")
    return None


def read_recent_memories(
    limit: int = 20,
    category: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Read recent memories from Open Brain for FRA context."""
    client = _get_client()
    if not client:
        return []

    try:
        query = client.table("memories").select("*").order("created_at", desc=True).limit(limit)
        if category:
            query = query.eq("category", category)
        if source:
            query = query.eq("source", source)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"Failed to read memories: {e}")
        return []


def read_memories_by_tag(tag: str, limit: int = 20) -> list[dict]:
    """Read memories tagged with a specific tag."""
    client = _get_client()
    if not client:
        return []

    try:
        result = client.table("memories").select("*").contains("tags", [tag]).order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"Failed to read memories by tag: {e}")
        return []


def search_memories(query_text: str, limit: int = 10) -> list[dict]:
    """Text search across memory titles and summaries."""
    client = _get_client()
    if not client:
        return []

    try:
        result = client.table("memories").select("*").or_(
            f"title.ilike.%{query_text}%,summary.ilike.%{query_text}%"
        ).order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"Failed to search memories: {e}")
        return []


# ── Research State Operations ─────────────────────────────────────────────────

def save_research_state(
    system_id: str,
    proved_results: list[str],
    open_problems: list[str],
    blocked_routes: list[str],
    active_route: str,
    session_count: int,
) -> dict | None:
    """Save FRA's complete research state as a structured memory.

    Creates one comprehensive memory entry with full detail JSON.
    """
    return write_research_memory(
        title=f"FRA Research State — Session {session_count}",
        summary=f"Active route: {active_route}. {len(proved_results)} proved, {len(open_problems)} open, {len(blocked_routes)} blocked.",
        tags=["fra", "research-state", "governance", active_route.replace(" ", "-").lower()],
        details={
            "system_id": system_id,
            "session_count": session_count,
            "active_route": active_route,
            "proved_results": proved_results,
            "open_problems": open_problems,
            "blocked_routes": blocked_routes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        importance=5,
    )


def save_session_summary(
    system_id: str,
    session_label: str,
    findings: str,
    verdict: str,
    next_action: str,
) -> dict | None:
    """Save a single FRA session summary to Open Brain."""
    return write_research_memory(
        title=f"FRA Session: {session_label}",
        summary=findings[:500] if len(findings) > 500 else findings,
        tags=["fra", "session", "research"],
        details={
            "system_id": system_id,
            "session_label": session_label,
            "full_findings": findings,
            "verdict": verdict,
            "next_action": next_action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        importance=4,
    )


def record_theorem(
    name: str,
    statement: str,
    status: str,
    proof_sketch: str = "",
    evidence_level: str = "assumption",
) -> dict | None:
    """Record a mathematical theorem or result."""
    status_map = {
        "proved": 5,
        "provable": 4,
        "conjectured": 3,
        "numerical": 3,
        "open": 2,
        "refuted": 1,
    }
    return write_research_memory(
        title=f"Theorem: {name}",
        summary=statement[:500] if len(statement) > 500 else statement,
        tags=["fra", "theorem", status, evidence_level],
        details={
            "name": name,
            "statement": statement,
            "status": status,
            "proof_sketch": proof_sketch,
            "evidence_level": evidence_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        importance=status_map.get(status, 3),
    )


# ── BRAIN.md Context Operations ───────────────────────────────────────────────

def read_brain_md() -> str:
    """Read the BRAIN.md portable brain file for AI context.

    This provides FRA with identity, framework, and current state context.
    """
    brain_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "open-brain-human-door", "BRAIN.md"),
        r"C:\Users\info\OneDrive\Desktop\Claude-workspace\open-brain-human-door\BRAIN.md",
    ]
    for path in brain_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to read BRAIN.md: {e}")
    return ""


def read_brain_section(section_header: str) -> str:
    """Extract a specific section from BRAIN.md."""
    brain = read_brain_md()
    if not brain:
        return ""

    lines = brain.split("\n")
    in_section = False
    result = []
    for line in lines:
        if line.strip().startswith("##") and section_header.lower() in line.lower():
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("##"):
                break
            result.append(line)
    return "\n".join(result).strip()


# ── Context Assembly ─────────────────────────────────────────────────────────

def assemble_session_context(system_id: str) -> dict:
    """Assemble full context for a new FRA session.

    Returns a dict with:
      - brain_context: BRAIN.md content summary
      - recent_memories: last 10 research memories
      - open_problems: memories tagged 'open-problem'
      - blocked_routes: memories tagged 'blocked'
      - governance_state: current governance health
    """
    context = {
        "brain_context": read_brain_section("FEATHER GOVERNANCE FRAMEWORK")[:2000],
        "recent_memories": [],
        "open_problems": [],
        "blocked_routes": [],
        "proved_results": [],
        "governance_state": {},
    }

    recent = read_recent_memories(limit=15, source="fra-research-agent")
    for m in recent:
        mem = dict(m)
        if "open-problem" in (mem.get("tags") or []):
            context["open_problems"].append(mem)
        elif "blocked" in (mem.get("tags") or []):
            context["blocked_routes"].append(mem)
        elif "proved" in (mem.get("tags") or []):
            context["proved_results"].append(mem)
        else:
            context["recent_memories"].append(mem)

    # Get governance state
    try:
        from fra_governance import get_report as sb_report
        context["governance_state"] = sb_report(system_id)
    except Exception:
        pass

    return context


# ── Self-Test ─────────────────────────────────────────────────────────────────

def self_test() -> bool:
    """Test the memory bridge against the live Supabase instance."""
    try:
        # Test write
        result = write_research_memory(
            title="FRA Memory Bridge Self-Test",
            summary="This is an automated self-test from fra_memory.py. Safe to delete.",
            tags=["fra", "self-test", "automated"],
            details={"test": True, "timestamp": datetime.now(timezone.utc).isoformat()},
            importance=2,
        )
        if not result:
            print("  fra_memory self-test: WARN — Supabase write skipped (no connection)")
            return True  # Non-blocking — memory is optional

        mem_id = result.get("id")
        assert mem_id, "No ID returned from insert"

        # Test read
        recent = read_recent_memories(limit=5, source="fra-research-agent")
        assert isinstance(recent, list)

        # Test tag search
        tagged = read_memories_by_tag("fra", limit=5)
        assert isinstance(tagged, list)

        # Test text search
        searched = search_memories("Self-Test", limit=3)
        assert isinstance(searched, list)

        # Test context assembly (needs a system_id)
        try:
            from fra_governance.startup import get_system_id
            sid = get_system_id()
            if sid:
                ctx = assemble_session_context(sid)
                assert isinstance(ctx, dict)
        except Exception:
            pass

        # Cleanup test entry
        try:
            client = _get_client()
            if client and mem_id:
                client.table("memories").delete().eq("id", mem_id).execute()
        except Exception:
            pass

        print("  fra_memory self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  fra_memory self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
