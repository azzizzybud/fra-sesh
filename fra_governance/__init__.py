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
from fra_governance.startup import (
    ensure_fra_registered, get_system_id as fra_system_id,
)
from fra_governance.fra_memory import (
    write_research_memory, read_recent_memories,
    save_research_state, save_session_summary,
    assemble_session_context, read_brain_md, self_test as memory_self_test,
)
from fra_governance.parallel_engine import (
    execute_parallel_tracks, build_standard_fra_tracks,
    merge_findings, ParallelResult, TrackDefinition, self_test as parallel_self_test,
)
from fra_governance.universal_research import (
    get_all_systems, get_system, get_active_systems,
    get_classification_summary, route_research_query,
    record_system_session, build_system_prompt,
    build_universal_dashboard, get_research_priority,
    get_theorems, get_route_labels, self_test as universal_self_test,
)
from fra_governance.fra_output import (
    evaluate_with_panel, humanize_text, humanize_score,
    research_to_content_brief, generate_video_asset_specs,
    process_fra_output, self_test as output_self_test,
)
from fra_governance.fra_consolidation import (
    list_components, find_fra_file, print_consolidation_report,
    get_fra_path, self_test as consolidation_self_test,
)
from fra_governance.vine_activation import (
    activate_vine_spawner, spawn_from_template,
    spawn_research_team, get_active_vine_agents, self_test as vine_activation_self_test,
)
from fra_governance.fra_marketing import (
    compute_stability_score, classify_lead, score_leads,
    generate_agency_metrics, generate_business_intelligence_report,
    generate_marketing_campaign_brief, self_test as marketing_self_test,
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
        "fra_memory": memory_self_test,
        "parallel_engine": parallel_self_test,
        "universal_research": universal_self_test,
        "fra_output": output_self_test,
        "fra_consolidation": consolidation_self_test,
        "vine_activation": vine_activation_self_test,
        "fra_marketing": marketing_self_test,
    }
    results = {}
    for name, test_fn in tests.items():
        try:
            results[name] = test_fn()
        except Exception as e:
            results[name] = False
            print(f"  {name} self-test: ERROR - {e}")
    return results
