"""
fra_governance/universal_research.py — Multi-System Research Orchestration

Generalizes FRA from RH-only research to all 10 systems in the Feather
Universal Balance Programme. Each system follows the same framework:
  S → E(S) > epsilon → find r in K(S) → E(S+r) <= epsilon

Systems registered:
  SYS-001: Riemann Zeta — Jensen Hyperbolicity (RH)
  SYS-002: Feather Kin Self-Application (meta)
  SYS-003: Quantum Gravity Unification
  SYS-004: Dark Sector Mass-Energy Gap
  SYS-005: Protein Folding (PRACTICALLY_SOLVED)
  SYS-006: P vs NP (STRUCTURAL_OBSTRUCTION)
  SYS-007: Consciousness Explanatory Gap (PHILOSOPHICAL)
  SYS-008: Market Equilibrium (STRUCTURAL_OBSTRUCTION — SMD)
  SYS-009: Goldbach Conjecture
  SYS-010: Navier-Stokes Regularity
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fra_governance.universal")

REGISTRY_PATH = os.environ.get(
    "UNIVERSAL_REGISTRY_PATH",
    r"C:\Users\info\OneDrive\Desktop\Claude-workspace\Feather Universal Balance Programme\00_Master_Archive\universal_systems_registry.json",
)


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class ResearchSystem:
    """A single research system from the universal registry."""
    sys_id: str
    name: str
    domain: str
    description: str  # S
    gap: str  # E_S
    epsilon: str
    reservoirs: list[dict]
    natural_reservoirs: list[dict]
    current_route: str = ""
    classification: str = "HIDDEN_PENDING"
    rh_not_proved: bool = False
    note: str = ""

    @property
    def is_active(self) -> bool:
        return self.classification in ("HIDDEN_PENDING", "NUMERICAL_ONLY", "PHILOSOPHICAL")

    @property
    def is_proved(self) -> bool:
        return self.classification == "PROVED_NATURAL"

    @property
    def is_blocked(self) -> bool:
        return self.classification == "STRUCTURAL_OBSTRUCTION"

    @property
    def is_solved(self) -> bool:
        return self.classification == "PRACTICALLY_SOLVED"


@dataclass
class SystemStatus:
    """Runtime status of a research system."""
    sys_id: str
    sessions_run: int = 0
    last_session: str = ""
    findings_count: int = 0
    open_routes: list[str] = field(default_factory=list)
    blocked_routes: list[str] = field(default_factory=list)
    proved_results: list[str] = field(default_factory=list)
    priority: int = 5  # 1-10, higher = more attention needed


# ── Registry Operations ───────────────────────────────────────────────────────

_registry_cache: dict | None = None


def load_registry() -> dict:
    """Load the universal systems registry from disk."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache

    if not os.path.exists(REGISTRY_PATH):
        logger.warning(f"Universal registry not found at {REGISTRY_PATH}")
        _registry_cache = {"systems": [], "theorems_discovered": [], "route_classifications": {}}
        return _registry_cache

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        _registry_cache = json.load(f)
    return _registry_cache


def get_all_systems() -> list[ResearchSystem]:
    """Get all 10 systems parsed from the registry."""
    registry = load_registry()
    systems = []
    for s in registry.get("systems", []):
        systems.append(ResearchSystem(
            sys_id=s["id"],
            name=s["name"],
            domain=s["domain"],
            description=s.get("S", ""),
            gap=s.get("E_S", ""),
            epsilon=s.get("epsilon", ""),
            reservoirs=s.get("R_S", []),
            natural_reservoirs=s.get("K_S", []),
            current_route=s.get("current_route", ""),
            classification=s.get("classification", "HIDDEN_PENDING"),
            rh_not_proved=s.get("rh_not_proved", False),
            note=s.get("note", ""),
        ))
    return systems


def get_system(sys_id: str) -> ResearchSystem | None:
    """Get a single system by ID."""
    for s in get_all_systems():
        if s.sys_id == sys_id:
            return s
    return None


def get_active_systems() -> list[ResearchSystem]:
    """Get systems that are still actively being researched (not proved/blocked)."""
    return [s for s in get_all_systems() if s.is_active]


def get_classification_summary() -> dict:
    """Summarize all systems by classification."""
    systems = get_all_systems()
    summary = {}
    for s in systems:
        c = s.classification
        if c not in summary:
            summary[c] = []
        summary[c].append(s.sys_id)
    return summary


def get_theorems() -> list[dict]:
    """Get all discovered theorems from the registry."""
    return load_registry().get("theorems_discovered", [])


def get_route_labels() -> dict:
    """Get route classification labels and meanings."""
    return load_registry().get("route_classifications", {})


# ── System Status Tracking ────────────────────────────────────────────────────

STATUS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "fra_system_status.json"
)


def load_system_statuses() -> dict[str, SystemStatus]:
    """Load per-system research status from disk."""
    if not os.path.exists(STATUS_PATH):
        return {}
    with open(STATUS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    result = {}
    for sid, data in raw.items():
        result[sid] = SystemStatus(
            sys_id=data.get("sys_id", sid),
            sessions_run=data.get("sessions_run", 0),
            last_session=data.get("last_session", ""),
            findings_count=data.get("findings_count", 0),
            open_routes=data.get("open_routes", []),
            blocked_routes=data.get("blocked_routes", []),
            proved_results=data.get("proved_results", []),
            priority=data.get("priority", 5),
        )
    return result


def save_system_statuses(statuses: dict[str, SystemStatus]):
    """Save per-system research status to disk."""
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    raw = {}
    for sid, st in statuses.items():
        raw[sid] = {
            "sys_id": st.sys_id,
            "sessions_run": st.sessions_run,
            "last_session": st.last_session,
            "findings_count": st.findings_count,
            "open_routes": st.open_routes,
            "blocked_routes": st.blocked_routes,
            "proved_results": st.proved_results,
            "priority": st.priority,
        }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


def record_system_session(
    sys_id: str,
    finding_type: str,
    description: str,
    evidence_level: str = "assumption",
):
    """Record a research session for a system."""
    statuses = load_system_statuses()
    if sys_id not in statuses:
        statuses[sys_id] = SystemStatus(sys_id=sys_id)

    st = statuses[sys_id]
    st.sessions_run += 1
    st.last_session = datetime.now(timezone.utc).isoformat()
    st.findings_count += 1

    if finding_type == "proved":
        st.proved_results.append(description)
    elif finding_type == "open":
        st.open_routes.append(description)
    elif finding_type == "blocked":
        st.blocked_routes.append(description)

    save_system_statuses(statuses)

    # Also write to Open Brain memory
    try:
        from fra_governance.fra_memory import write_research_memory
        system = get_system(sys_id)
        sys_name = system.name if system else sys_id
        write_research_memory(
            title=f"[{sys_id}] {sys_name}: {finding_type.upper()} — {description[:80]}",
            summary=description,
            tags=["fra", "universal", sys_id, finding_type],
            details={
                "system_id": sys_id,
                "system_name": sys_name,
                "finding_type": finding_type,
                "evidence_level": evidence_level,
                "session_number": st.sessions_run,
            },
            importance=4 if finding_type == "proved" else 3,
        )
    except Exception:
        pass


# ── Research Router ───────────────────────────────────────────────────────────

def route_research_query(query: str) -> list[ResearchSystem]:
    """Route a natural-language query to relevant research systems.

    Simple keyword-based routing. For production use, this would use embeddings.
    """
    systems = get_all_systems()
    query_lower = query.lower()

    keyword_map = {
        "riemann": ["SYS-001"],
        "zeta": ["SYS-001"],
        "jensen": ["SYS-001"],
        "prime": ["SYS-001", "SYS-009"],
        "number theory": ["SYS-001", "SYS-009"],
        "quantum": ["SYS-003"],
        "gravity": ["SYS-003"],
        "dark matter": ["SYS-004"],
        "dark energy": ["SYS-004"],
        "cosmology": ["SYS-004"],
        "protein": ["SYS-005"],
        "folding": ["SYS-005"],
        "p vs np": ["SYS-006"],
        "complexity": ["SYS-006"],
        "consciousness": ["SYS-007"],
        "qualia": ["SYS-007"],
        "market": ["SYS-008"],
        "equilibrium": ["SYS-008"],
        "economics": ["SYS-008"],
        "goldbach": ["SYS-009"],
        "navier": ["SYS-010"],
        "stokes": ["SYS-010"],
        "fluid": ["SYS-010"],
        "feather": ["SYS-002"],
        "meta": ["SYS-002"],
    }

    matched_ids = set()
    for keyword, ids in keyword_map.items():
        if keyword in query_lower:
            matched_ids.update(ids)

    if not matched_ids:
        # Return active systems by default
        return get_active_systems()

    return [s for s in systems if s.sys_id in matched_ids]


def get_research_priority() -> list[dict]:
    """Get systems ordered by research priority.

    Active systems (HIDDEN_PENDING) with most sessions rank highest.
    Blocked/solved systems rank lowest.
    """
    statuses = load_system_statuses()
    systems = get_all_systems()

    prioritized = []
    for s in systems:
        st = statuses.get(s.sys_id, SystemStatus(sys_id=s.sys_id))
        score = 0
        if s.is_active:
            score += 100
        if s.classification == "NUMERICAL_ONLY":
            score += 50
        score += st.sessions_run  # More activity = higher priority
        if st.proved_results:
            score += len(st.proved_results) * 10  # Productive systems

        prioritized.append({
            "sys_id": s.sys_id,
            "name": s.name,
            "classification": s.classification,
            "sessions_run": st.sessions_run,
            "findings_count": st.findings_count,
            "open_routes": len(st.open_routes),
            "proved_results": len(st.proved_results),
            "priority_score": score,
        })

    prioritized.sort(key=lambda x: x["priority_score"], reverse=True)
    return prioritized


# ── Research Prompt Builder ───────────────────────────────────────────────────

def build_system_prompt(sys_id: str) -> str:
    """Build a research prompt for a specific system using the Feather framework."""
    system = get_system(sys_id)
    if not system:
        return f"System {sys_id} not found in registry."

    statuses = load_system_statuses()
    st = statuses.get(sys_id, SystemStatus(sys_id=sys_id))

    prompt = f"""# FRA Universal Research — {system.name} ({sys_id})
Domain: {system.domain}
Classification: {system.classification}

## THE OPEN SYSTEM (S)
{system.description}

## THE GAP (E_S)
{system.gap}

## TOLERANCE (epsilon)
{system.epsilon}

## POSSIBLE RESERVOIRS (R_S)
"""
    for r in system.reservoirs:
        prompt += f"- {r['name']} ({r['type']})\n"

    prompt += "\n## NATURAL RESERVOIRS (K_S)\n"
    for r in system.natural_reservoirs:
        prompt += f"- {r['name']}: {r['status']}"
        if r.get("blocker"):
            prompt += f" — BLOCKER: {r['blocker']}"
        prompt += "\n"

    if system.note:
        prompt += f"\n## FEATHER ANALYSIS\n{system.note}\n"

    prompt += f"""
## RESEARCH STATUS
- Sessions run: {st.sessions_run}
- Proved results: {len(st.proved_results)}
- Open routes: {len(st.open_routes)}
- Blocked routes: {len(st.blocked_routes)}

## MA'AT AUDIT
1. Truth: What is actually known here (not assumed)?
2. Fair-share: Is the gap honestly characterized?
3. Right-size: Is the proposed approach proportionate?
4. Lasting value: Does this advance the programme?

The honest record matters more than an impressive result.
"""
    return prompt


# ── Dashboard ─────────────────────────────────────────────────────────────────

def build_universal_dashboard() -> dict:
    """Build a comprehensive research dashboard across all systems."""
    systems = get_all_systems()
    statuses = load_system_statuses()
    classification_summary = get_classification_summary()
    theorems = get_theorems()

    total_sessions = sum(st.sessions_run for st in statuses.values())
    total_findings = sum(st.findings_count for st in statuses.values())
    total_proved = sum(len(st.proved_results) for st in statuses.values())

    systems_detail = []
    for s in systems:
        st = statuses.get(s.sys_id, SystemStatus(sys_id=s.sys_id))
        systems_detail.append({
            "id": s.sys_id,
            "name": s.name,
            "domain": s.domain,
            "classification": s.classification,
            "is_active": s.is_active,
            "sessions": st.sessions_run,
            "findings": st.findings_count,
            "open_routes": len(st.open_routes),
            "proved": len(st.proved_results),
            "blocked": len(st.blocked_routes),
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_systems": len(systems),
            "active_systems": sum(1 for s in systems if s.is_active),
            "proved_natural": sum(1 for s in systems if s.is_proved),
            "structural_obstruction": sum(1 for s in systems if s.is_blocked),
            "practically_solved": sum(1 for s in systems if s.is_solved),
            "total_sessions": total_sessions,
            "total_findings": total_findings,
            "total_proved": total_proved,
            "theorems_discovered": len(theorems),
        },
        "classification_summary": classification_summary,
        "systems": systems_detail,
        "theorems": theorems,
        "route_labels": get_route_labels(),
    }


# ── Self-Test ─────────────────────────────────────────────────────────────────

def self_test() -> bool:
    """Test the universal research module."""
    try:
        # Test registry loading
        systems = get_all_systems()
        assert len(systems) == 10, f"Expected 10 systems, got {len(systems)}"
        assert systems[0].sys_id == "SYS-001"

        # Test system lookup
        rh = get_system("SYS-001")
        assert rh is not None
        assert "Riemann" in rh.name

        # Test classification summary
        summary = get_classification_summary()
        assert len(summary) > 0

        # Test active systems
        active = get_active_systems()
        assert len(active) > 0

        # Test research routing
        routed = route_research_query("riemann hypothesis")
        assert any(s.sys_id == "SYS-001" for s in routed)

        routed_physics = route_research_query("quantum gravity and dark matter")
        assert any(s.sys_id == "SYS-003" for s in routed_physics)

        # Test prompt building
        prompt = build_system_prompt("SYS-001")
        assert "Riemann" in prompt
        assert "MA'AT AUDIT" in prompt

        # Test status recording
        record_system_session("SYS-001", "open", "Test session from self-test")
        statuses = load_system_statuses()
        assert "SYS-001" in statuses
        assert statuses["SYS-001"].sessions_run >= 1

        # Test dashboard
        dashboard = build_universal_dashboard()
        assert dashboard["summary"]["total_systems"] == 10
        assert len(dashboard["systems"]) == 10
        assert "theorems" in dashboard

        # Test priority
        priorities = get_research_priority()
        assert len(priorities) == 10
        assert priorities[0]["priority_score"] >= priorities[-1]["priority_score"]

        # Test theorems
        theorems = get_theorems()
        assert len(theorems) >= 5

        # Test route labels
        labels = get_route_labels()
        assert "PROVED_NATURAL" in labels
        assert "STRUCTURAL_OBSTRUCTION" in labels

        print("  universal_research self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  universal_research self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
