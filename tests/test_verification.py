"""Tests for the verification ensemble and voting rule (RFC-0002)."""

from app.config import Settings
from app.schemas import (
    ClaimCreate,
    ClaimStatus,
    Effect,
    EffectDirection,
    Intervention,
    ModelVerdict,
    Source,
    StudyType,
    VerdictType,
)
from app.services import build_draft_claim, verify_claim_llm
from app.verification import apply_voting, verify_claim


def _verdict(verdict: VerdictType, confidence: float) -> ModelVerdict:
    return ModelVerdict(model="m", verdict=verdict, confidence=confidence)


def _claim(subject: str, direction: EffectDirection):
    data = ClaimCreate(
        subject=subject,
        population="adults",
        intervention=Intervention(description="dose"),
        outcome="strength",
        effect=Effect(direction=direction),
        sources=[
            Source(study_id="s", pmid_or_doi="d", study_type=StudyType.meta_analysis, year=2021)
        ],
    )
    return build_draft_claim(data)


def _stub_settings(**overrides) -> Settings:
    base = dict(
        openrouter_api_key="",  # force stub
        verifier_models=["m1", "m2", "m3"],
        verify_threshold=0.75,
    )
    base.update(overrides)
    return Settings(**base)


# --- voting rule ----------------------------------------------------------- #
def test_voting_all_pass_above_threshold_auto_verifies():
    verdicts = [_verdict(VerdictType.passed, 0.9) for _ in range(3)]
    status, _rule, mean = apply_voting(verdicts, 0.75)
    assert status == ClaimStatus.auto_verified
    assert mean >= 0.75


def test_voting_any_fail_rejects():
    verdicts = [_verdict(VerdictType.passed, 0.9), _verdict(VerdictType.failed, 0.9)]
    status, _rule, _mean = apply_voting(verdicts, 0.75)
    assert status == ClaimStatus.rejected


def test_voting_low_confidence_holds():
    verdicts = [_verdict(VerdictType.passed, 0.5) for _ in range(3)]
    status, _rule, _mean = apply_voting(verdicts, 0.75)
    assert status == ClaimStatus.held


def test_voting_mixed_uncertain_holds():
    verdicts = [_verdict(VerdictType.passed, 0.9), _verdict(VerdictType.uncertain, 0.9)]
    status, _rule, _mean = apply_voting(verdicts, 0.75)
    assert status == ClaimStatus.held


def test_voting_empty_holds():
    status, _rule, _mean = apply_voting([], 0.75)
    assert status == ClaimStatus.held


# --- verdict parsing ------------------------------------------------------- #
def test_model_verdict_parses_from_raw_dict():
    raw = {
        "model": "x",
        "verdict": "pass",
        "confidence": 0.88,
        "field_quotes": [
            {"field": "subject", "supported": True, "source_quote": "creatine ...", "confidence": 0.9}
        ],
        "proposed_downgrades": ["small_sample"],
        "notes": "ok",
    }
    verdict = ModelVerdict.model_validate(raw)
    assert verdict.verdict == VerdictType.passed
    assert verdict.field_quotes[0].field == "subject"


# --- stub ensemble end to end --------------------------------------------- #
def test_stub_verify_publishes_faithful_claim():
    claim = _claim("creatine", EffectDirection.increase)
    source = "A meta-analysis found creatine increased strength by 8%."
    record = verify_claim(claim, source, _stub_settings())
    assert record.decision_status == ClaimStatus.auto_verified
    assert record.models == ["m1", "m2", "m3"]
    assert len(record.per_model_verdicts) == 3


def test_stub_verify_holds_unrelated_source():
    claim = _claim("creatine", EffectDirection.increase)
    source = "Iron supplementation improved hemoglobin in anemic patients."
    record = verify_claim(claim, source, _stub_settings())
    assert record.decision_status == ClaimStatus.held


def test_verify_claim_llm_sets_status_and_provenance():
    claim = _claim("creatine", EffectDirection.increase)
    source = "A meta-analysis found creatine increased strength by 8%."
    updated = verify_claim_llm(claim, source, _stub_settings())
    assert updated.status == ClaimStatus.published
    assert updated.verified_by == "llm:ensemble"
    assert updated.verification.decision_status == ClaimStatus.auto_verified
