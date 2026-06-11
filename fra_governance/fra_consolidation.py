"""
fra_governance/fra_consolidation.py — FRA File Consolidation (#8)

Creates a unified FRA module registry that maps all scattered FRA files
across the workspace into a single namespace. Provides discoverability
and import paths without moving physical files.

Locations consolidated:
  - odysseus/fra_governance/    → FRA governance modules (primary)
  - feather-research-agent/     → FRA orchestrator + agent specs
  - feather-research-agent1/    → FRA mirror + Cloudflare
  - RH/                         → FRA research scripts + JT programme
  - Feather Universal Balance/  → Universal research registry
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Consolidated Path Registry ────────────────────────────────────────────────

FRA_LOCATIONS = {
    "governance": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\odysseus\fra_governance",
    "orchestrator": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent\05_research\RH",
    "research_scripts": r"C:\Users\info\OneDrive\Desktop\RH",
    "mirror": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent1",
    "universal": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\Feather Universal Balance Programme",
    "core": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent",
    "odysseus": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\odysseus",
    "cowork": r"C:\Users\info\OneDrive\Desktop\Claude-workspace\Feather-Cowork\Feather Research  Agent",
}


def get_fra_path(component: str) -> str:
    """Get the filesystem path for an FRA component."""
    return FRA_LOCATIONS.get(component, "")


def list_components() -> dict:
    """List all consolidated FRA components with existence status."""
    result = {}
    for name, path in FRA_LOCATIONS.items():
        exists = os.path.exists(path)
        result[name] = {
            "path": path,
            "exists": exists,
        }
    return result


def find_fra_file(filename: str) -> list[str]:
    """Search all FRA locations for a filename. Returns matching paths."""
    matches = []
    for name, path in FRA_LOCATIONS.items():
        if not os.path.exists(path):
            continue
        for f in Path(path).rglob(filename):
            matches.append(str(f))
    return matches


def add_all_to_syspath():
    """Add all FRA locations to sys.path for cross-module imports."""
    for path in FRA_LOCATIONS.values():
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)


def print_consolidation_report() -> str:
    """Generate a human-readable consolidation report."""
    components = list_components()
    lines = ["# FRA File Consolidation Report", ""]
    lines.append(f"Total components tracked: {len(components)}")
    lines.append(f"Active (exists): {sum(1 for c in components.values() if c.get('exists'))}")
    lines.append("")

    for name, info in sorted(components.items()):
        status = "FOUND" if info.get("exists") else "NOT FOUND"
        lines.append(f"  {name}: {status} at {info['path']}")

    lines.append("")
    lines.append("Key FRA orchestration files:")
    for f in ["fra_rh_orchestrator.md", "fra_prompt.md", "fra_agent1_weil_guinand.md"]:
        found = find_fra_file(f)
        lines.append(f"  {f}: {'FOUND' if found else 'MISSING'} ({len(found)} copies)")

    return "\n".join(lines)


def self_test() -> bool:
    """Test the consolidation module."""
    try:
        components = list_components()
        assert len(components) >= 5
        assert components.get("governance", {}).get("exists")

        # Verify find works on governance
        found = find_fra_file("sandwich_bridge.py")
        assert len(found) >= 1, f"Expected sandwich_bridge.py found, got {found}"

        # Quick path check
        governance_path = get_fra_path("governance")
        assert os.path.exists(governance_path)

        # Verify report works
        report = print_consolidation_report()
        assert "FRA File Consolidation Report" in report

        print("  fra_consolidation self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  fra_consolidation self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if self_test() else 1)
