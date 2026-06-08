"""
fra_governance — Vine/SBT Mathematical Governance for FRA
Integrated into Odysseus as an AI governance layer.

Six modules, each derived from a proven mathematical theorem:
  cauchy_ledger      — Triple-entry audit trail (source·flow - loss)
  chamber_monitor    — Ordered chamber enforcement (q_1 >= q_2 >= ...)
  baseline_tracker   — Geometric baseline anomaly detection (R = B - B_geo)
  cost_function      — AM-GM cost penalty (deviation from optimal)
  bezoutian_verifier — Determinant integrity check (Bezoutian structure)
  repair_pipeline    — Self-healing via quarantine and re-spawn
  vine_spawner       — Agent creation from vine strand templates
  sandwich_bridge     — External AI governance gateway (7 X-layers)
"""

from fra_governance.cauchy_ledger import (
    record, verify_entry, verify_agent, get_agent_history,
    set_chamber_status, get_balance_sheet, self_test as cauchy_self_test,
)
from fra_governance.chamber_monitor import (
    register_agent, check_chamber, check_parity, get_chamber_status,
    self_test as chamber_self_test,
)
from fra_governance.baseline_tracker import (
    establish_baseline, observe, get_agent_health, get_system_health,
    self_test as baseline_self_test,
)
from fra_governance.cost_function import (
    set_optimal, compute_cost, get_guidance,
    self_test as cost_self_test,
)
from fra_governance.bezoutian_verifier import (
    register_response, check_minor_sequence, record_interaction,
    get_structural_health, self_test as bezoutian_self_test,
)
from fra_governance.repair_pipeline import (
    detect_failure, repair_agent, get_health_report,
    self_test as repair_self_test,
)
from fra_governance.vine_spawner import (
    spawn_agent, verify_vine_output, get_agent_tree,
    compute_scale_complexity, self_test as vine_self_test,
)
from fra_governance.sandwich_bridge import (
    register_fra_sesh, process_request, get_report, self_test as sandwich_self_test,
)

def run_all_self_tests():
    """Run all governance module self-tests. Returns dict of results."""
    tests = {
        "cauchy_ledger": cauchy_self_test,
        "chamber_monitor": chamber_self_test,
        "baseline_tracker": baseline_self_test,
        "cost_function": cost_self_test,
        "bezoutian_verifier": bezoutian_self_test,
        "repair_pipeline": repair_self_test,
        "vine_spawner": vine_self_test,
        "sandwich_bridge": sandwich_self_test,
    }
    results = {}
    for name, test_fn in tests.items():
        try:
            results[name] = test_fn()
        except Exception as e:
            results[name] = False
            print(f"  {name} self-test: ERROR - {e}")
    return results
