"""Consensus Engine (RFC-0001 §6).

Defines ONE formula for ``consensus_confidence`` so the value means the same
thing everywhere:

    confidence = agreement * evidence_weight(best level in majority group)

where ``agreement`` is the fraction of Claims sharing the majority effect
direction. When Claims on the same subject+outcome disagree, the value is
additionally capped at 0.5 so conflict is always visible (RFC-0001 §6).
"""

from __future__ import annotations

from collections import Counter

from app.schemas import (
    Claim,
    EvidenceLevel,
    OutcomeConsensus,
    SubstanceSummary,
)

_EVIDENCE_WEIGHT: dict[EvidenceLevel, float] = {
    EvidenceLevel.high: 0.95,
    EvidenceLevel.moderate: 0.80,
    EvidenceLevel.low: 0.60,
    EvidenceLevel.very_low: 0.40,
}

_LEVEL_ORDER: list[EvidenceLevel] = [
    EvidenceLevel.very_low,
    EvidenceLevel.low,
    EvidenceLevel.moderate,
    EvidenceLevel.high,
]

_CONFLICT_CAP = 0.5


def _best_level(claims: list[Claim]) -> EvidenceLevel:
    return max(claims, key=lambda c: _LEVEL_ORDER.index(c.evidence_level)).evidence_level


def is_conflicting(claims: list[Claim]) -> bool:
    directions = {c.effect.direction for c in claims}
    return len(directions) > 1


def consensus_confidence(claims: list[Claim]) -> float:
    """Confidence that the majority effect direction reflects the evidence.

    Works for a single Claim (agreement = 1.0) and for a group.
    """
    if not claims:
        return 0.0

    directions = Counter(c.effect.direction for c in claims)
    majority_direction, majority_count = directions.most_common(1)[0]
    agreement = majority_count / len(claims)

    majority_claims = [c for c in claims if c.effect.direction == majority_direction]
    weight = _EVIDENCE_WEIGHT[_best_level(majority_claims)]

    confidence = round(agreement * weight, 2)
    if is_conflicting(claims):
        confidence = min(confidence, _CONFLICT_CAP)
    return confidence


def summarise_subject(subject: str, published_claims: list[Claim]) -> SubstanceSummary:
    """Aggregate published Claims for a subject into per-outcome consensus."""
    by_outcome: dict[str, list[Claim]] = {}
    for claim in published_claims:
        by_outcome.setdefault(claim.outcome.strip().lower(), []).append(claim)

    outcomes: list[OutcomeConsensus] = []
    for claims in by_outcome.values():
        outcomes.append(
            OutcomeConsensus(
                outcome=claims[0].outcome,
                evidence_level=_best_level(claims),
                consensus_confidence=consensus_confidence(claims),
                conflicting=is_conflicting(claims),
                claims=claims,
            )
        )

    outcomes.sort(key=lambda o: o.consensus_confidence, reverse=True)
    return SubstanceSummary(
        subject=subject,
        published_claims=len(published_claims),
        outcomes=outcomes,
    )
