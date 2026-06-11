"""
fra_governance/vine_activation.py — Vine Spawner Activation (#9)

Wires the mathematically-determined vine_spawner.py strand templates
into active agent creation. Previously, agent spawning was ad-hoc.
Now it uses deterministic strand cardinalities from Vine Decomposition:

  2x2 vine: 52/21/6 (k=3), 295/120/36/8 (k=4), 1730/710/220/55/10 (k=5)
  3x3 vine: 57/12 (all k=3,4,5)

This module connects vine_spawner to the FRA agent creation flow
and provides the activation API.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fra_governance.vine_activation")


# ── Vine Strand Templates ─────────────────────────────────────────────────────

VINE_TEMPLATES = {
    "research_supervisor": {
        "scale": 2,
        "strands": [
            {"name": "state_reader", "cardinality": 52, "role": "Reads current research state and assembles context"},
            {"name": "gap_analyzer", "cardinality": 21, "role": "Identifies the most tractable open gap"},
            {"name": "route_finder", "cardinality": 6, "role": "Proposes a specific computation or proof approach"},
        ],
        "description": "3-strand research supervisor from 2x2 vine at k=3",
    },
    "numerical_runner": {
        "scale": 2,
        "strands": [
            {"name": "script_writer", "cardinality": 52, "role": "Writes computational scripts for numerical verification"},
            {"name": "executor", "cardinality": 21, "role": "Runs scripts and captures output"},
            {"name": "interpreter", "cardinality": 6, "role": "Reads results and determines numerical verdict"},
        ],
        "description": "3-strand numerical runner from 2x2 vine at k=3",
    },
    "analytical_prover": {
        "scale": 2,
        "strands": [
            {"name": "symbolic_engine", "cardinality": 52, "role": "Attempts symbolic/algebraic proof steps"},
            {"name": "hamburger_checker", "cardinality": 21, "role": "Checks if expression reduces to a known positive form"},
            {"name": "evidence_labeler", "cardinality": 6, "role": "Labels each claim with evidence level"},
        ],
        "description": "3-strand analytical prover from 2x2 vine at k=3",
    },
    "parallel_coordinator": {
        "scale": 3,
        "strands": [
            {"name": "track_dispatcher", "cardinality": 57, "role": "Dispatches tracks and manages concurrency"},
            {"name": "result_collector", "cardinality": 12, "role": "Collects results and merges findings"},
        ],
        "description": "2-strand parallel coordinator from 3x3 vine (invariant across k=3,4,5)",
    },
    "full_research_team": {
        "scale": 2,
        "strands": [
            {"name": "supervisor", "cardinality": 295, "role": "Orchestrator that manages the full research pipeline"},
            {"name": "state_reader", "cardinality": 120, "role": "Reads and updates research state"},
            {"name": "gap_analyzer", "cardinality": 36, "role": "Identifies specific open gaps"},
            {"name": "route_finder", "cardinality": 8, "role": "Proposes proof approaches for the identified gap"},
        ],
        "description": "4-strand full research team from 2x2 vine at k=4",
    },
}


@dataclass
class VineAgent:
    """A spawned vine agent."""
    agent_id: str
    template_name: str
    strand_name: str
    role: str
    cardinality: int
    scale: int
    status: str = "idle"
    spawned_at: str = ""
    evidence_level: str = "assumption"


def activate_vine_spawner() -> dict:
    """Activate the vine spawner for deterministic agent creation.

    This registers available templates and prepares the spawner
    for use in FRA agent creation flows.
    """
    from fra_governance.vine_spawner import spawn_agent, get_agent_tree, compute_scale_complexity

    results = {
        "templates_available": len(VINE_TEMPLATES),
        "templates": {},
    }

    for name, template in VINE_TEMPLATES.items():
        complexity = compute_scale_complexity(template["scale"])
        results["templates"][name] = {
            "scale": template["scale"],
            "strands": len(template["strands"]),
            "total_cardinality": sum(s["cardinality"] for s in template["strands"]),
            "complexity": complexity,
            "description": template["description"],
        }

    return results


def spawn_from_template(
    template_name: str,
    system_id: str | None = None,
) -> list[VineAgent]:
    """Spawn agents deterministically from a vine template.

    Uses vine_spawner.py's mathematically-determined strand cardinalities.
    No guesswork — the number and complexity of sub-agents is determined
    by the Vine Decomposition Theorem.
    """
    from fra_governance.vine_spawner import spawn_agent

    if template_name not in VINE_TEMPLATES:
        logger.warning(f"Template '{template_name}' not found. Available: {list(VINE_TEMPLATES.keys())}")
        return []

    template = VINE_TEMPLATES[template_name]
    agents = []

    for i, strand in enumerate(template["strands"]):
        result = spawn_agent(
            scale=template["scale"],
            vine_type="2x2" if template["scale"] == 2 else "3x3",
            base_priority=1.0 / (i + 1),
        )

        agents.append(VineAgent(
            agent_id=result.get("agent_id", str(hash(f"{template_name}_{strand['name']}"))),
            template_name=template_name,
            strand_name=strand["name"],
            role=strand["role"],
            cardinality=strand["cardinality"],
            scale=template["scale"],
            status="spawned",
            spawned_at=datetime.now(timezone.utc).isoformat(),
        ))

    logger.info(f"Spawned {len(agents)} agents from template '{template_name}'")
    return agents


def spawn_research_team(problem_description: str) -> list[VineAgent]:
    """Spawn a full research team for a given problem.

    Decides which template to use based on problem complexity.
    """
    word_count = len(problem_description.split())

    if word_count < 100:
        template = "numerical_runner"
    elif word_count < 500:
        template = "research_supervisor"
    elif word_count < 1000:
        template = "analytical_prover"
    else:
        template = "full_research_team"

    return spawn_from_template(template)


def get_active_vine_agents() -> list[dict]:
    """Get all active vine-spawned agents and their status."""
    from fra_governance.vine_spawner import get_agent_tree

    tree = get_agent_tree()
    return tree if isinstance(tree, list) else []


def verify_vine_output(agent_id: str, output: dict) -> dict:
    """Verify output from a vine-spawned agent against structural invariants."""
    from fra_governance.vine_spawner import verify_vine_output

    return verify_vine_output(agent_id, output)


def self_test() -> bool:
    """Test vine activation."""
    try:
        # Test template loading
        assert len(VINE_TEMPLATES) >= 3

        # Test activation
        activation = activate_vine_spawner()
        assert activation["templates_available"] >= 3

        # Test spawning (2x2 vine at k=3 produces 3 strands)
        agents = spawn_from_template("research_supervisor")
        assert len(agents) == 3

        # Test problem-based spawning
        team = spawn_research_team("Short problem")
        assert len(team) > 0

        print("  vine_activation self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  vine_activation self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
