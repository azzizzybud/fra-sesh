"""
fra_governance/fra_marketing.py — Business Intelligence Integration (#10)

Connects the AI Agency SBT Strategy to FRA governance.
Applies SBT (Stability Balance Theorem) intelligence to:
  - Lead stability scoring
  - Client health monitoring
  - Reactivation timing optimization
  - Network influence mapping

Bridges FRA's mathematical governance layer with the business/marketing
layer defined in AI_Agency_SBT_Strategy.md.

3 pricing tiers:
  Foundation (EUR997/mo) — Database reactivation
  Intelligence (EUR1,997/mo) — SBT scoring + analytics
  Franchise Network (EUR3,997/mo) — Multi-location + network mapping
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fra_governance.marketing")


# ── Business Data Types ───────────────────────────────────────────────────────

@dataclass
class LeadProfile:
    """A business lead with SBT stability scoring."""
    lead_id: str
    name: str
    industry: str
    location_count: int = 1
    stability_score: float = 0.0  # 0-100, SBT-derived
    reactivation_window: str = ""  # Optimal timing window
    health_status: str = "unscored"  # "healthy", "at_risk", "critical"
    last_contact: str = ""
    notes: str = ""


@dataclass
class AgencyMetrics:
    """AI Agency operational metrics integrated with FRA."""
    total_leads: int = 0
    scored_leads: int = 0
    average_stability: float = 0.0
    at_risk_clients: int = 0
    healthy_clients: int = 0
    reactivation_opportunities: int = 0
    monthly_revenue_estimate: float = 0.0


PRICING_TIERS = {
    "foundation": {"price_eur": 997, "features": ["database_reactivation", "review_automation", "lead_nurture"]},
    "intelligence": {"price_eur": 1997, "features": ["all_foundation", "sbt_scoring", "health_monitoring", "timing_optimization"]},
    "franchise": {"price_eur": 3997, "features": ["all_intelligence", "network_mapping", "multi_location", "franchise_analytics"]},
}

TARGET_VERTICALS = ["med_spa", "fitness", "HVAC", "dental"]


# ── Stability Scoring Engine ──────────────────────────────────────────────────

def compute_stability_score(
    client_data: dict,
    governance_state: dict | None = None,
) -> float:
    """Compute a 0-100 stability score using SBT principles.

    SBT spectral dominance: P(sigma) = S(1/2)/S(sigma)
    Applied to business: ratio of current health to optimal health.

    Factors:
      - Recency of last interaction (higher = more stable)
      - Frequency of interactions
      - Response rate
      - Revenue trend
      - Governance health (from FRA)
    """
    score = 50.0  # Baseline

    # Recency bonus (last 30 days = high, >90 days = low)
    recency_days = client_data.get("days_since_last_contact", 90)
    if recency_days <= 7:
        score += 20
    elif recency_days <= 30:
        score += 10
    elif recency_days > 90:
        score -= 15
    elif recency_days > 180:
        score -= 25

    # Frequency bonus
    monthly_interactions = client_data.get("monthly_interactions", 0)
    score += min(monthly_interactions * 3, 15)

    # Response rate
    response_rate = client_data.get("response_rate", 0.5)
    score += (response_rate - 0.5) * 20

    # Revenue trend
    revenue_trend = client_data.get("revenue_trend", 0.0)  # -1 to +1
    score += revenue_trend * 10

    # Governance health bonus (if FRA is healthy, business intelligence improves)
    if governance_state:
        health = governance_state.get("health", {})
        if health.get("status") == "healthy":
            score += 5

    return max(0.0, min(100.0, score))


def classify_lead(score: float) -> str:
    """Classify a lead based on stability score."""
    if score >= 70:
        return "healthy"
    elif score >= 40:
        return "stable"
    elif score >= 20:
        return "at_risk"
    else:
        return "critical"


def compute_reactivation_window(score: float, last_contact_days: int) -> str:
    """Compute optimal reactivation timing window.

    Based on SBT: the window where marginal return of contact is highest.
    """
    if score >= 70 and last_contact_days <= 30:
        return "now — peak stability, upsell window"
    elif score >= 40 and last_contact_days <= 90:
        return "within 2 weeks — stable, check-in recommended"
    elif score >= 20:
        return "within 1 week — at risk, intervention needed"
    else:
        return "immediately — critical, potential loss imminent"


# ── Agency Operations ─────────────────────────────────────────────────────────

def score_leads(leads: list[dict]) -> list[LeadProfile]:
    """Score a batch of leads through the SBT intelligence layer."""
    from fra_governance.startup import get_system_id
    from fra_governance import get_report as sb_report

    system_id = get_system_id()
    gov_state = sb_report(system_id) if system_id else None

    profiles = []
    for lead in leads:
        score = compute_stability_score(lead, gov_state)
        profile = LeadProfile(
            lead_id=lead.get("id", str(hash(lead.get("name", "")))),
            name=lead.get("name", "Unknown"),
            industry=lead.get("industry", "unknown"),
            location_count=lead.get("locations", 1),
            stability_score=score,
            reactivation_window=compute_reactivation_window(
                score, lead.get("days_since_last_contact", 90)
            ),
            health_status=classify_lead(score),
            last_contact=lead.get("last_contact", ""),
        )
        profiles.append(profile)

    # Sort by urgency (lowest score first — most critical)
    profiles.sort(key=lambda p: p.stability_score)
    return profiles


def generate_agency_metrics(profiles: list[LeadProfile]) -> AgencyMetrics:
    """Generate agency-level metrics from scored leads."""
    metrics = AgencyMetrics(
        total_leads=len(profiles),
        scored_leads=len([p for p in profiles if p.stability_score > 0]),
        average_stability=sum(p.stability_score for p in profiles) / max(len(profiles), 1),
        at_risk_clients=sum(1 for p in profiles if p.health_status == "at_risk"),
        healthy_clients=sum(1 for p in profiles if p.health_status == "healthy"),
        reactivation_opportunities=sum(1 for p in profiles if p.stability_score < 40),
    )

    # Revenue estimate based on pricing tiers and location count
    for p in profiles:
        if p.location_count == 1:
            metrics.monthly_revenue_estimate += PRICING_TIERS["intelligence"]["price_eur"]
        elif p.location_count <= 5:
            metrics.monthly_revenue_estimate += PRICING_TIERS["intelligence"]["price_eur"] * p.location_count * 0.8
        else:
            metrics.monthly_revenue_estimate += PRICING_TIERS["franchise"]["price_eur"]

    return metrics


def generate_business_intelligence_report(profiles: list[LeadProfile]) -> dict:
    """Generate a full business intelligence report for the AI Agency."""
    metrics = generate_agency_metrics(profiles)

    criticals = [p for p in profiles if p.health_status == "critical"]
    at_risks = [p for p in profiles if p.health_status == "at_risk"]
    healthies = [p for p in profiles if p.health_status == "healthy"]

    # Generate tactical recommendations
    recommendations = []
    if criticals:
        recommendations.append({
            "priority": "URGENT",
            "action": f"Contact {len(criticals)} critical clients immediately",
            "clients": [p.name for p in criticals[:5]],
            "expected_impact": f"Prevent loss of ~EUR{len(criticals) * 997}/mo",
        })
    if at_risks:
        recommendations.append({
            "priority": "HIGH",
            "action": f"Schedule check-ins for {len(at_risks)} at-risk clients within 1 week",
            "clients": [p.name for p in at_risks[:5]],
            "expected_impact": f"Stabilize ~EUR{len(at_risks) * 997}/mo revenue",
        })
    if healthies:
        recommendations.append({
            "priority": "MEDIUM",
            "action": f"Upsell opportunity for {len(healthies)} healthy clients",
            "clients": [p.name for p in healthies[:3]],
            "expected_impact": f"Move to Intelligence tier: +EUR{len(healthies) * 1000}/mo potential",
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "total_leads": metrics.total_leads,
            "average_stability": round(metrics.average_stability, 1),
            "healthy": metrics.healthy_clients,
            "at_risk": metrics.at_risk_clients,
            "critical": len(criticals),
            "reactivation_opportunities": metrics.reactivation_opportunities,
            "estimated_monthly_revenue": round(metrics.monthly_revenue_estimate),
        },
        "pricing_tiers": PRICING_TIERS,
        "target_verticals": TARGET_VERTICALS,
        "recommendations": recommendations,
        "top_critical": [{"name": p.name, "score": p.stability_score, "industry": p.industry} for p in criticals[:5]],
        "top_healthy": [{"name": p.name, "score": p.stability_score, "industry": p.industry} for p in healthies[:5]],
    }


# ── Content Marketing Intelligence ────────────────────────────────────────────

def generate_marketing_campaign_brief(
    vertical: str,
    lead_count: int,
    profiles: list[LeadProfile] | None = None,
) -> dict:
    """Generate a marketing campaign brief for a target vertical.

    Uses SBT intelligence to determine optimal messaging and timing.
    """
    vertical_configs = {
        "med_spa": {"pain_point": "Booking gaps between Botox cycles", "hook": "Your client database is leaking revenue between appointments"},
        "fitness": {"pain_point": "Member churn after 90 days", "hook": "90% of your ex-members would come back — if you asked at the right time"},
        "HVAC": {"pain_point": "Seasonal gaps in service calls", "hook": "Your service truck is driving past 200 past clients every day"},
        "dental": {"pain_point": "Recall system leakage", "hook": "Half your patients are overdue for a cleaning and don't know it"},
    }

    config = vertical_configs.get(vertical, vertical_configs["med_spa"])

    avg_score = sum(p.stability_score for p in profiles) / max(len(profiles), 1) if profiles else 50

    brief = {
        "vertical": vertical,
        "lead_count": lead_count,
        "pain_point": config["pain_point"],
        "hook": config["hook"],
        "lead_magnet": f"Free Database Stability Audit — see exactly which {lead_count} contacts are ready to rebook",
        "pricing_tier": "intelligence" if avg_score < 60 else "foundation",
        "pricing_eur": PRICING_TIERS["intelligence"]["price_eur"] if avg_score < 60 else PRICING_TIERS["foundation"]["price_eur"],
        "urgency": "high" if avg_score < 40 else "medium",
        "sbt_angle": f"Average stability score: {avg_score:.0f}/100 — {'significant reactivation opportunity' if avg_score < 50 else 'stable base with upsell potential'}",
    }

    return brief


# ── Self-Test ─────────────────────────────────────────────────────────────────

def self_test() -> bool:
    """Test the marketing intelligence module."""
    try:
        # Test stability scoring
        lead = {"name": "Test Med Spa", "industry": "med_spa", "locations": 1, "days_since_last_contact": 15, "monthly_interactions": 4, "response_rate": 0.7, "revenue_trend": 0.3}
        score = compute_stability_score(lead)
        assert 60 <= score <= 90, f"Expected score 60-90, got {score}"
        assert classify_lead(score) in ("healthy", "stable")

        # Test reactivation window
        window = compute_reactivation_window(score, 15)
        assert len(window) > 0

        # Test lead scoring batch
        leads = [
            {"name": "Healthy Spa", "industry": "med_spa", "locations": 2, "days_since_last_contact": 7, "monthly_interactions": 6, "response_rate": 0.9, "revenue_trend": 0.5},
            {"name": "At Risk Gym", "industry": "fitness", "locations": 1, "days_since_last_contact": 120, "monthly_interactions": 1, "response_rate": 0.2, "revenue_trend": -0.3},
            {"name": "Critical HVAC", "industry": "HVAC", "locations": 3, "days_since_last_contact": 200, "monthly_interactions": 0, "response_rate": 0.0, "revenue_trend": -0.8},
        ]
        profiles = score_leads(leads)
        assert len(profiles) == 3
        assert profiles[0].stability_score <= profiles[-1].stability_score  # Sorted by urgency (lowest first)

        # Test agency metrics
        metrics = generate_agency_metrics(profiles)
        assert metrics.total_leads == 3
        assert metrics.at_risk_clients + metrics.healthy_clients <= 3

        # Test business intelligence report
        report = generate_business_intelligence_report(profiles)
        assert "metrics" in report
        assert "recommendations" in report

        # Test marketing campaign brief
        brief = generate_marketing_campaign_brief("med_spa", 50, profiles)
        assert brief["vertical"] == "med_spa"
        assert "lead_magnet" in brief

        # Test pricing tiers
        assert PRICING_TIERS["foundation"]["price_eur"] == 997
        assert PRICING_TIERS["intelligence"]["price_eur"] == 1997
        assert PRICING_TIERS["franchise"]["price_eur"] == 3997

        print("  fra_marketing self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  fra_marketing self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
