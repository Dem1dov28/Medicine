"""Evidence Engine — GRADE-lite (RFC-0001 §3).

Deliberately a simplified, explicit approximation of GRADE. The evidence level
is computed here by rules, never provided by the LLM (RFC-0000 first principle:
"LLM is a probabilistic extractor, not an authority").
"""

from __future__ import annotations

from app.schemas import EvidenceLevel, Source, StudyType

# RFC-0001 §3: base level per study design.
_BASE_LEVEL: dict[StudyType, EvidenceLevel] = {
    StudyType.meta_analysis: EvidenceLevel.high,
    StudyType.systematic_review: EvidenceLevel.high,
    StudyType.rct: EvidenceLevel.moderate,
    StudyType.cohort: EvidenceLevel.low,
    StudyType.observational: EvidenceLevel.low,
    StudyType.case_series: EvidenceLevel.very_low,
    StudyType.expert_opinion: EvidenceLevel.very_low,
}

# Ordered weakest -> strongest so we can move between adjacent levels.
_ORDER: list[EvidenceLevel] = [
    EvidenceLevel.very_low,
    EvidenceLevel.low,
    EvidenceLevel.moderate,
    EvidenceLevel.high,
]


def base_evidence_level(sources: list[Source]) -> EvidenceLevel:
    """Highest base level among the supporting sources.

    A Claim is only as strong as its best evidence design; downgrades are then
    applied on top of that (see :func:`downgrade`).
    """
    if not sources:
        raise ValueError("a Claim needs at least one source")
    best = max(_ORDER.index(_BASE_LEVEL[s.study_type]) for s in sources)
    return _ORDER[best]


def downgrade(level: EvidenceLevel, steps: int = 1) -> EvidenceLevel:
    """Lower an evidence level by ``steps`` (never below very_low)."""
    idx = max(0, _ORDER.index(level) - steps)
    return _ORDER[idx]


def evidence_level_for_claim(
    sources: list[Source],
    *,
    small_sample: bool = False,
    high_heterogeneity: bool = False,
) -> EvidenceLevel:
    """Compute evidence level for a Claim.

    Downgrade flags (RFC-0001 §3) are supplied by the human verifier in v0 —
    they are not auto-detected yet. Conflict-of-interest is tracked as a flag
    elsewhere and intentionally does not auto-downgrade here.
    """
    level = base_evidence_level(sources)
    steps = int(small_sample) + int(high_heterogeneity)
    return downgrade(level, steps) if steps else level
