"""Unit tests for the Consensus Engine (RFC-0001 §6)."""

from app.consensus import consensus_confidence, is_conflicting, summarise_subject
from app.schemas import (
    Claim,
    ClaimStatus,
    Effect,
    EffectDirection,
    EvidenceLevel,
    Intervention,
    Source,
    StudyType,
)


def _claim(direction: EffectDirection, level: EvidenceLevel) -> Claim:
    return Claim(
        subject="creatine",
        population="adults",
        intervention=Intervention(description="5 g/day"),
        outcome="muscle strength",
        effect=Effect(direction=direction),
        evidence_level=level,
        consensus_confidence=0.0,
        sources=[
            Source(study_id="s", pmid_or_doi="d", study_type=StudyType.rct, year=2020)
        ],
        status=ClaimStatus.published,
        verified_by="tester",
    )


def test_single_high_claim_confidence():
    c = _claim(EffectDirection.increase, EvidenceLevel.high)
    assert consensus_confidence([c]) == 0.95


def test_agreeing_claims_keep_confidence():
    claims = [
        _claim(EffectDirection.increase, EvidenceLevel.high),
        _claim(EffectDirection.increase, EvidenceLevel.moderate),
    ]
    assert not is_conflicting(claims)
    assert consensus_confidence(claims) == 0.95


def test_conflicting_claims_capped():
    claims = [
        _claim(EffectDirection.increase, EvidenceLevel.high),
        _claim(EffectDirection.decrease, EvidenceLevel.high),
    ]
    assert is_conflicting(claims)
    assert consensus_confidence(claims) <= 0.5


def test_summary_groups_by_outcome_and_flags_conflict():
    claims = [
        _claim(EffectDirection.increase, EvidenceLevel.high),
        _claim(EffectDirection.decrease, EvidenceLevel.high),
    ]
    summary = summarise_subject("creatine", claims)
    assert summary.published_claims == 2
    assert len(summary.outcomes) == 1
    assert summary.outcomes[0].conflicting is True
