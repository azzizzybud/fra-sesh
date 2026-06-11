"""
fra_governance/fra_output.py — FRA Output Pipeline

Triple integration:
  #5: Feather Accountability Panel as meta-governance
      Evaluates FRA research outputs through the 4-persona lens
      (Partner/Advisor/Colleague/Friend) before publication.

  #6: Content Studio pipeline connector
      Routes FRA plain-language summaries into the Feather Content
      Studio format (script → ElevenLabs → Higgsfield → Seedance).

  #7: Humanizer integration
      Runs Agent 3 output through AI-detection removal patterns
      before publication to human-read channels.

The output pipeline runs after every significant FRA session:
  1. Raw findings → Humanizer polish → Panel evaluation → Publish/Revise
  2. Panel-approved findings → Content Studio brief → Video production assets
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fra_governance.output")


# ═══════════════════════════════════════════════════════════════════════════════
# #5: FEATHER ACCOUNTABILITY PANEL — META-GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PanelVerdict:
    """Structural verdict from one Feather Panel persona."""
    persona: str  # "partner", "advisor", "colleague", "friend"
    verdict: str  # Brief, punchy structural reading
    drift_flag: bool = False  # True if Isfet/drift detected
    maat_score: int = 3  # 1-5, Ma'at alignment
    recommendation: str = ""


@dataclass
class PanelEvaluation:
    """Complete Feather Panel evaluation of an FRA output."""
    output_title: str
    partner: PanelVerdict
    advisor: PanelVerdict
    colleague: PanelVerdict
    friend: PanelVerdict
    agreed_recommendation: str = ""
    publish_approved: bool = False
    revision_needed: str = ""

    @property
    def has_drift(self) -> bool:
        return any(p.drift_flag for p in [self.partner, self.advisor, self.colleague, self.friend])

    @property
    def avg_maat_score(self) -> float:
        scores = [self.partner.maat_score, self.advisor.maat_score, self.colleague.maat_score, self.friend.maat_score]
        return sum(scores) / 4


def evaluate_with_panel(
    output_title: str,
    output_content: str,
    domain: str = "research",
) -> PanelEvaluation:
    """Run FRA output through the Feather Accountability Panel.

    This is the meta-governance layer — before any FRA finding is published
    to memory, content studio, or human-facing channels, it passes through
    the 4-persona structural evaluation.

    Returns a PanelEvaluation with publish_approved flag.
    """
    content_lower = output_content.lower()

    # ── Partner (Ma'at Lens): Pattern-holder ──
    # Checks: proportion, pattern integrity, structural soundness
    partner_drift = False
    partner_maat = 3

    overclaim_markers = [
        "proved rh", "rh is proved", "riemann hypothesis proved",
        "solved rh", "complete proof", "definitive proof",
    ]
    for marker in overclaim_markers:
        if marker in content_lower:
            partner_drift = True
            partner_maat = 1

    uncertainty_markers = ["might", "possibly", "could be", "perhaps", "potentially", "appears to"]
    uncertainty_count = sum(1 for m in uncertainty_markers if m in content_lower)

    if uncertainty_count > 8:
        partner_drift = True
        partner_maat = 2

    evidence_markers = ["proved", "formally_verified", "test_success", "numerical", "runtime_success", "assumption"]
    has_evidence_label = any(m in content_lower for m in evidence_markers)

    if not has_evidence_label and len(output_content) > 500:
        partner_drift = True
        partner_maat = 2

    partner_verdict = _build_partner_verdict(output_title, partner_drift, partner_maat, has_evidence_label)

    # ── Advisor (Isfet Lens): Drift-namer ──
    advisor_drift = False
    advisor_maat = 3

    hype_markers = [
        "breakthrough", "revolutionary", "groundbreaking", "unprecedented",
        "game-changing", "paradigm shift", "historic",
    ]
    hype_count = sum(1 for m in hype_markers if m in content_lower)

    if hype_count > 2:
        advisor_drift = True
        advisor_maat = 2

    if any(w in content_lower for w in ["obviously", "clearly", "undoubtedly", "without question"]):
        advisor_drift = True
        advisor_maat = 2

    advisor_verdict = _build_advisor_verdict(advisor_drift, advisor_maat, hype_count)

    # ── Colleague (Ka Lens): Capacity-auditor ──
    colleague_drift = False
    colleague_maat = 3

    word_count = len(output_content.split())
    if word_count > 3000:
        colleague_drift = True
        colleague_maat = 2

    technical_terms = len(re.findall(r'\b(?:theorem|lemma|proof|proposition|corollary|conjecture|hypothesis|axiom)\b', content_lower))
    if technical_terms > 15 and word_count < 500:
        colleague_drift = True
        colleague_maat = 2

    colleague_verdict = _build_colleague_verdict(colleague_drift, colleague_maat, word_count)

    # ── Friend (Ab Lens): Heart-reader ──
    friend_drift = False
    friend_maat = 3

    deflection_markers = [
        "further research needed", "more work remains", "future work",
        "beyond the scope", "left as exercise",
    ]
    deflection_count = sum(1 for m in deflection_markers if m in content_lower)

    if deflection_count > 3:
        friend_drift = True
        friend_maat = 2

    if "honest" in content_lower and deflection_count > 1:
        friend_drift = True
        friend_maat = 2

    friend_verdict = _build_friend_verdict(friend_drift, friend_maat, deflection_count)

    # ── Agreed Recommendation ──
    any_drift = partner_drift or advisor_drift or colleague_drift or friend_drift
    avg_score = (partner_maat + advisor_maat + colleague_maat + friend_maat) / 4

    if any_drift and avg_score < 2.0:
        agreed = f"BLOCKED. Overclaim or structural drift detected. Revise before publishing."
        approved = False
        revision = "Remove overclaims, add evidence labels, reduce hype markers, shorten if over 3000 words."
    elif any_drift:
        agreed = f"REVISE. Minor drift patterns detected. Address flagged items and resubmit."
        approved = False
        revision = "Address flagged drift markers. Partner/Audit will recheck."
    else:
        agreed = f"APPROVED. Output passes Ma'at structural checks. Ready for publication."
        approved = True
        revision = ""

    return PanelEvaluation(
        output_title=output_title,
        partner=PanelVerdict("partner", partner_verdict, partner_drift, partner_maat),
        advisor=PanelVerdict("advisor", advisor_verdict, advisor_drift, advisor_maat),
        colleague=PanelVerdict("colleague", colleague_verdict, colleague_drift, colleague_maat),
        friend=PanelVerdict("friend", friend_verdict, friend_drift, friend_maat),
        agreed_recommendation=agreed,
        publish_approved=approved,
        revision_needed=revision,
    )


def _build_partner_verdict(title: str, drift: bool, maat: int, has_evidence: bool) -> str:
    if drift and maat <= 1:
        return f"BLOCKED: '{title}' contains overclaim markers (e.g., 'proved RH'). The Feather framework explicitly forbids this. RH is not proved."
    if drift and maat == 2:
        return f"FLAG: '{title}' lacks evidence labels or leans on vague uncertainty. Structural integrity requires precision — name what is proved, numerical, and open separately."
    if not has_evidence:
        return f"CHECK: '{title}' has no evidence taxonomy labels (proved/numerical/assumption). Add them."
    return f"PASS: '{title}' reads structurally sound. Proportion is right. No overclaim detected."


def _build_advisor_verdict(drift: bool, maat: int, hype_count: int) -> str:
    if drift and hype_count > 3:
        return f"DRIFT: {hype_count} hype markers found ('breakthrough', 'revolutionary', etc.). This is performance, not research. Strip the hype."
    if drift:
        return "DRIFT: 'Obviously'/'clearly' detected — these mask uncertainty. Name what is actually known and what isn't."
    return "PASS: No hype drift detected. Language matches the evidence level presented."


def _build_colleague_verdict(drift: bool, maat: int, word_count: int) -> str:
    if drift and word_count > 3000:
        return f"CAPACITY WARNING: {word_count} words exceeds the workable range for a single output. Break into sections or condense."
    if drift:
        return "CAPACITY CHECK: Too many technical terms packed into too little explanation. Right-size the output."
    return "PASS: Output size is proportionate to the content density."


def _build_friend_verdict(drift: bool, maat: int, deflection_count: int) -> str:
    if drift and deflection_count > 3:
        return f"DEFLECTION: {deflection_count} 'further research needed' markers — this is avoidance, not honesty. Say what IS known, not what isn't."
    if drift:
        return "DEFLECTION: 'Honest' framing used with deflection markers — the Ab is conflicted. State the actual blocker directly."
    return "PASS: Output reads direct and honest. No deflection pattern detected."


# ═══════════════════════════════════════════════════════════════════════════════
# #6: CONTENT STUDIO PIPELINE CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ContentBrief:
    """A Feather Content Studio brief derived from FRA research output."""
    title: str
    angle: str
    format: str  # "short_form" | "long_form" | "social"
    hook_type: str = "curiosity_gap"
    script_sections: list[dict] = field(default_factory=list)
    elevenlabs_voice: str = "Sterling"
    elevenlabs_settings: dict = field(default_factory=lambda: {
        "stability": 50,
        "similarity_boost": 75,
        "style_exaggeration": 0,
        "speed": 100,
    })
    target_runtime_seconds: int = 0
    target_word_count: int = 0


def research_to_content_brief(
    title: str,
    findings: str,
    format: str = "short_form",
) -> ContentBrief:
    """Convert FRA plain-language findings into a Content Studio production brief.

    This is the bridge between FRA research output and the Feather Content
    Studio video pipeline (script → ElevenLabs → Higgsfield → Seedance).
    """
    word_count = len(findings.split())

    # Determine format sizing
    if format == "short_form":
        target_runtime = 60  # 60 seconds
        target_words = 150  # ~150 wpm for short form
    elif format == "long_form":
        target_runtime = 600  # 10 minutes
        target_words = 1500
    else:  # social
        target_runtime = 30
        target_words = 75

    # Build script sections from findings
    sections = _build_script_sections(findings, format)

    # Determine hook type based on content
    hook = "curiosity_gap"
    if "proved" in findings.lower() or "discovered" in findings.lower():
        hook = "authority_open"
    elif "?" in findings:
        hook = "curiosity_gap"
    elif any(w in findings.lower() for w in ["you", "your", "we", "our"]):
        hook = "identity_mirror"

    return ContentBrief(
        title=title,
        angle=f"Feather Research: {title[:80]}",
        format=format,
        hook_type=hook,
        script_sections=sections,
        target_runtime_seconds=target_runtime,
        target_word_count=target_words,
    )


def _build_script_sections(findings: str, format: str) -> list[dict]:
    """Decompose findings into the 6-section Feather script structure."""
    paragraphs = [p.strip() for p in findings.split("\n\n") if p.strip()]

    sections = []

    # Hook (first 2-3 sentences)
    hook_text = " ".join(paragraphs[0].split()[:50]) if paragraphs else ""
    sections.append({"name": "Hook", "order": 1, "content": hook_text})

    # Trap (rest of first paragraph or second paragraph)
    trap_text = paragraphs[1][:200] if len(paragraphs) > 1 else ""
    sections.append({"name": "Trap", "order": 2, "content": trap_text})

    # Feather Framework (core finding)
    framework_text = paragraphs[2][:300] if len(paragraphs) > 2 else paragraphs[0][:300]
    sections.append({"name": "Feather Framework", "order": 3, "content": framework_text})

    # Four Measures
    remaining = paragraphs[3:] if len(paragraphs) > 3 else paragraphs[1:]
    measures_text = " ".join(p[:100] for p in remaining[:4])
    sections.append({"name": "Four Measures", "order": 4, "content": measures_text})

    # Integration
    sections.append({"name": "Integration", "order": 5, "content": "This is what the Feather framework reveals about the structure."})

    # Close
    close_text = paragraphs[-1][:200] if paragraphs else ""
    sections.append({"name": "Close", "order": 6, "content": close_text or "Ma'at is the measure."})

    return sections


def generate_video_asset_specs(brief: ContentBrief) -> dict:
    """Generate Higgsfield/Seedance asset specifications from a content brief.

    These are production-ready prompts for the content pipeline:
    - Character reference stills (Banana Pro)
    - Scene plates (Seedance)
    - Thumbnail specs
    """
    return {
        "character_still": {
            "tool": "Higgsfield Banana Pro",
            "mode": "Mode 1A",
            "description": "Kemetic figure, West African features, black linen, gold Ma'at feather pendant. Full body on white seamless studio background. Photorealistic.",
        },
        "thumbnail": {
            "tool": "Higgsfield Soul Cinema",
            "mode": "GPT-2 Face Detail",
            "description": f"Chest-up portrait, obsidian background, gold feather pendant glow. Title overlay area reserved. Subject: {brief.title[:60]}",
        },
        "seedance_scenes": [
            {
                "mode": "M1 Narrative",
                "description": f"Character direct-to-camera, warm-lit study, speaking about {brief.angle[:50]}",
                "duration_seconds": brief.target_runtime_seconds // 3,
            },
            {
                "mode": "M5 Atmospheric",
                "description": "Temple colonnade at dawn, feather on golden scale, establishing shot",
                "duration_seconds": 10,
            },
        ],
        "elevenlabs": {
            "voice": brief.elevenlabs_voice,
            "settings": brief.elevenlabs_settings,
            "format": "SSML",
            "target_wpm": 150,
        },
        "script": {
            "sections": brief.script_sections,
            "target_word_count": brief.target_word_count,
            "target_runtime": brief.target_runtime_seconds,
            "hook_type": brief.hook_type,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# #7: HUMANIZER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

# AI-writing patterns to detect and fix (from Wikipedia's "Signs of AI writing")
AI_PATTERNS = {
    "em_dash": (r"—", "—"),
    "ai_vocabulary": [
        "delve", "tapestry", "vibrant", "landscape", "realm",
        "moreover", "furthermore", "consequently", "thus",
        "it is worth noting", "it should be noted", "interestingly",
        "crucial", "paramount", "essential", "fundamentally",
    ],
    "passive_voice": [
        r"\b(can be seen|can be observed|it has been shown|it was found)\b",
    ],
    "filler_phrases": [
        "in today's world", "in the modern era", "in recent years",
        "it is important to", "one might argue", "some may say",
    ],
    "rule_of_three": [
        r"\b\w+,\s+\w+,\s+and\s+\w+\b",
    ],
    "inflated_symbolism": [
        r"\b(profound|deeply|richly)\s+(symbolic|meaningful|significant)",
    ],
}


def humanize_text(text: str, intensity: str = "medium") -> str:
    """Remove AI-generated writing patterns from text.

    Based on Wikipedia's comprehensive "Signs of AI writing" guide.
    Intensity levels:
      "light" — only remove obvious AI vocabulary
      "medium" — remove vocabulary + passive voice + filler
      "heavy" — full rewrite: all patterns

    Returns humanized text with a score.
    """
    original_word_count = len(text.split())
    fixed = text

    replacements = 0

    # Level 1: Remove AI vocabulary (always)
    for word in AI_PATTERNS["ai_vocabulary"]:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        count_before = len(pattern.findall(fixed))
        if word in ("delve",):
            fixed = pattern.sub("explore", fixed)
        elif word in ("tapestry",):
            fixed = pattern.sub("pattern", fixed)
        elif word in ("vibrant",):
            fixed = pattern.sub("rich", fixed)
        elif word in ("realm",):
            fixed = pattern.sub("field", fixed)
        elif word in ("moreover", "furthermore"):
            fixed = pattern.sub("also", fixed)
        elif word in ("consequently", "thus"):
            fixed = pattern.sub("so", fixed)
        elif word in ("crucial", "paramount", "essential", "fundamentally"):
            fixed = pattern.sub("important", fixed)
        else:
            fixed = pattern.sub("", fixed)
        replacements += count_before

    # Level 2: Passive voice + filler (medium+)
    if intensity in ("medium", "heavy"):
        for phrase in AI_PATTERNS["passive_voice"]:
            pattern = re.compile(phrase, re.IGNORECASE)
            count = len(pattern.findall(fixed))
            fixed = pattern.sub("", fixed)
            replacements += count

        for phrase in AI_PATTERNS["filler_phrases"]:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            count = len(pattern.findall(fixed))
            fixed = pattern.sub("", fixed)
            replacements += count

    # Level 3: Full rewrite (heavy)
    if intensity == "heavy":
        # Remove em dashes
        fixed = fixed.replace("—", ", ").replace("  ", " ")
        replacements += fixed.count("—")

        # Break up rule-of-three patterns
        for pattern in AI_PATTERNS["rule_of_three"]:
            matches = re.findall(pattern, fixed)
            replacements += len(matches)

        # Remove inflated symbolism
        for pattern in AI_PATTERNS["inflated_symbolism"]:
            pattern_obj = re.compile(pattern, re.IGNORECASE)
            count = len(pattern_obj.findall(fixed))
            fixed = pattern_obj.sub("", fixed)
            replacements += count

    # Clean up double spaces and empty punctuation
    fixed = re.sub(r'  +', ' ', fixed)
    fixed = re.sub(r'\.\s*\.', '.', fixed)
    fixed = fixed.strip()

    new_word_count = len(fixed.split())
    word_loss_pct = ((original_word_count - new_word_count) / max(original_word_count, 1)) * 100

    return fixed


def humanize_score(text: str) -> dict:
    """Score text for AI-writing patterns without modifying it.

    Returns a humanization score (0-100) where higher = more human-like.
    """
    score = 100
    issues = []

    # Check AI vocabulary
    for word in AI_PATTERNS["ai_vocabulary"]:
        count = len(re.findall(r'\b' + re.escape(word) + r'\b', text, re.IGNORECASE))
        if count > 0:
            score -= count * 3
            issues.append(f"AI vocab: '{word}' ({count}x)")

    # Check em dashes
    em_dash_count = text.count("—")
    if em_dash_count > 2:
        score -= (em_dash_count - 2) * 2
        issues.append(f"Em dash overuse: {em_dash_count}")

    # Check passive voice
    for phrase in AI_PATTERNS["passive_voice"]:
        count = len(re.findall(phrase, text, re.IGNORECASE))
        if count > 0:
            score -= count * 2

    # Check filler
    for phrase in AI_PATTERNS["filler_phrases"]:
        if phrase.lower() in text.lower():
            score -= 5
            issues.append(f"Filler: '{phrase}'")

    return {
        "humanization_score": max(0, score),
        "issues_found": issues,
        "rating": _score_to_rating(score),
    }


def _score_to_rating(score: int) -> str:
    if score >= 90:
        return "natural — reads human"
    elif score >= 70:
        return "mostly human — minor AI artifacts"
    elif score >= 50:
        return "mixed — noticeable AI patterns"
    elif score >= 30:
        return "AI-heavy — needs significant revision"
    else:
        return "generated — clearly AI-written"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATED PIPELINE: Panel → Humanize → Content Studio
# ═══════════════════════════════════════════════════════════════════════════════

def process_fra_output(
    title: str,
    raw_findings: str,
    domain: str = "research",
    humanize_intensity: str = "medium",
    content_format: str = "short_form",
    system_id: str | None = None,
) -> dict:
    """Full FRA output pipeline — panel evaluation + humanization + content brief.

    This is the single entry point for processing any FRA session output:
    1. Panel evaluates structural integrity (governance gate)
    2. Humanizer removes AI artifacts (if panel approves)
    3. Content Studio brief generated (if panel approves)
    4. Results saved to Open Brain memory

    Returns the complete processing result.
    """
    logger.info(f"Processing FRA output: '{title}' ({len(raw_findings)} chars)")

    # Step 1: Panel Evaluation (meta-governance gate)
    panel = evaluate_with_panel(title, raw_findings, domain)

    # Step 2: Humanize (only if panel doesn't block)
    humanized = ""
    humanize_result = {}
    if panel.publish_approved or panel.avg_maat_score >= 2.5:
        humanized = humanize_text(raw_findings, intensity=humanize_intensity)
        humanize_result = humanize_score(humanized)
    else:
        humanized = raw_findings

    # Step 3: Content Studio Brief
    brief = None
    asset_specs = None
    if panel.publish_approved:
        brief = research_to_content_brief(
            title=title,
            findings=humanized or raw_findings,
            format=content_format,
        )
        asset_specs = generate_video_asset_specs(brief)

    # Step 4: Save to Open Brain
    memory_result = None
    try:
        from fra_governance.fra_memory import write_research_memory
        memory_result = write_research_memory(
            title=f"FRA Output: {title}",
            summary=humanized[:500] if humanized else raw_findings[:500],
            tags=["fra", "output", "panel-evaluated", "humanized", domain],
            details={
                "title": title,
                "raw_findings": raw_findings[:3000],
                "humanized": humanized[:3000] if humanized else "",
                "panel_evaluation": {
                    "approved": panel.publish_approved,
                    "maat_score": panel.avg_maat_score,
                    "has_drift": panel.has_drift,
                    "verdict": panel.agreed_recommendation,
                },
                "humanize_score": humanize_result.get("humanization_score"),
                "content_format": content_format,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            importance=4 if panel.publish_approved else 3,
        )
    except Exception as e:
        logger.warning(f"Failed to save output to memory: {e}")

    return {
        "title": title,
        "status": "approved" if panel.publish_approved else "needs_revision",
        "panel_evaluation": {
            "approved": panel.publish_approved,
            "maat_score": round(panel.avg_maat_score, 1),
            "has_drift": panel.has_drift,
            "verdict": panel.agreed_recommendation,
            "persona_verdicts": {
                "partner": panel.partner.verdict,
                "advisor": panel.advisor.verdict,
                "colleague": panel.colleague.verdict,
                "friend": panel.friend.verdict,
            },
        },
        "humanize_result": humanize_result,
        "content_brief": {
            "title": brief.title if brief else "",
            "angle": brief.angle if brief else "",
            "format": brief.format if brief else "",
            "hook_type": brief.hook_type if brief else "",
            "target_runtime": brief.target_runtime_seconds if brief else 0,
            "sections": len(brief.script_sections) if brief else 0,
            "asset_specs": asset_specs,
        } if brief else None,
        "memory_saved": memory_result is not None,
        "humanized_text": humanized[:500] + ("..." if len(humanized) > 500 else "") if humanized else "",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════════

def self_test() -> bool:
    """Test the full output pipeline."""
    try:
        # Test humanizer
        ai_text = "This is a revolutionary breakthrough. Furthermore, it delves into the profound and deeply symbolic landscape of prime numbers. It is worth noting that this could be a paradigm shift. One might argue that more research is needed — indeed, it is crucial."
        humanized = humanize_text(ai_text, "medium")
        assert "revolutionary" in humanized  # Not an AI vocab word
        assert len(humanized) < len(ai_text)  # Should remove words

        score = humanize_score(ai_text)
        assert "humanization_score" in score
        assert score["humanization_score"] < 90  # Should detect AI patterns

        # Test panel evaluation
        good_finding = "Lemma 5 is now PROVED via Hamburger theorem. Evidence level: provable. The remaining open step is the analytic derivation of constants C_a and K. RH is not proved."
        panel = evaluate_with_panel("Lemma 5 Proof", good_finding)
        assert panel.publish_approved
        assert panel.avg_maat_score >= 3

        bad_finding = "We have PROVED the Riemann Hypothesis. This is a revolutionary breakthrough. Obviously the solution is complete. Further research needed undoubtedly."
        panel2 = evaluate_with_panel("RH Proof", bad_finding)
        assert not panel2.publish_approved
        assert panel2.has_drift

        # Test content brief generation
        brief = research_to_content_brief(
            "Lemma 5: Hamburger Connection",
            "We found that the d=1 Jensen-Turan discriminant is equivalent to a Hankel determinant of the M-moment sequence. This means the base case is provable via Hamburger's theorem.",
            "short_form",
        )
        assert brief.title
        assert brief.format == "short_form"
        assert len(brief.script_sections) > 0

        # Test asset spec generation
        specs = generate_video_asset_specs(brief)
        assert "character_still" in specs
        assert "seedance_scenes" in specs
        assert "elevenlabs" in specs

        # Test full pipeline
        result = process_fra_output(
            "Hamburger Connection Found",
            "The d=1 Jensen-Turan discriminant is equivalent to a 3x3 Hankel determinant of the M-moment sequence, which is PSD by Hamburger's theorem. Evidence level: provable. RH is not proved.",
            domain="research",
        )
        assert result["status"] in ("approved", "needs_revision")
        assert "panel_evaluation" in result
        assert "humanize_result" in result

        print("  fra_output self-test: ALL PASS")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  fra_output self-test: ERROR - {e}")
        return False


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_test() else 1)
