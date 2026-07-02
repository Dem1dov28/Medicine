"""Application services: the orchestration between engines and storage.

This is where the RFC-0000 principle "LLM is not an authority" is enforced:
evidence level and consensus confidence are always (re)computed by the engines
when a Claim is built, never taken from caller input.
"""

from __future__ import annotations

from uuid import UUID

from app.config import Settings, get_settings
from app.consensus import consensus_confidence
from app.evidence import evidence_level_for_claim
from app.schemas import Claim, ClaimCreate, ClaimStatus, DowngradeFlag
from app.verification import verify_claim as run_verification


def build_draft_claim(
    data: ClaimCreate,
    *,
    small_sample: bool = False,
    high_heterogeneity: bool = False,
) -> Claim:
    """Turn extracted fields into a draft Claim with computed evidence level."""
    level = evidence_level_for_claim(
        data.sources,
        small_sample=small_sample,
        high_heterogeneity=high_heterogeneity,
    )

    claim = Claim(
        **data.model_dump(),
        evidence_level=level,
        consensus_confidence=0.0,  # placeholder; set below once level is known
        status=ClaimStatus.draft,
    )
    # Single-claim confidence (agreement = 1.0) weighted by its evidence level.
    claim.consensus_confidence = consensus_confidence([claim])
    return claim


def _aggregate_downgrades(record) -> tuple[bool, bool]:
    """Downgrade flags are applied only if a majority of models proposed them."""
    n = len(record.per_model_verdicts) or 1
    counts = {DowngradeFlag.small_sample: 0, DowngradeFlag.high_heterogeneity: 0}
    for verdict in record.per_model_verdicts:
        for flag in set(verdict.proposed_downgrades):
            counts[flag] = counts.get(flag, 0) + 1
    majority = n / 2
    return counts[DowngradeFlag.small_sample] > majority, counts[
        DowngradeFlag.high_heterogeneity
    ] > majority


def verify_claim_llm(
    claim: Claim, source_text: str, settings: Settings | None = None
) -> Claim:
    """Autonomous LLM verification (RFC-0002), replacing the human gate.

    The ensemble decides pass/hold/reject; the Evidence Engine re-applies any
    downgrade flags the ensemble proposed (LLM proposes, engine decides).
    """
    settings = settings or get_settings()
    record = run_verification(claim, source_text, settings)

    small_sample, high_heterogeneity = _aggregate_downgrades(record)
    claim.evidence_level = evidence_level_for_claim(
        claim.sources,
        small_sample=small_sample,
        high_heterogeneity=high_heterogeneity,
    )

    claim.verification = record
    claim.verified_by = "llm:ensemble"

    # published is only reachable through an auto_verified ensemble decision.
    if record.decision_status == ClaimStatus.auto_verified:
        claim.status = ClaimStatus.published
    else:
        claim.status = record.decision_status  # held or rejected

    # Recompute consensus confidence after any evidence-level change.
    claim.consensus_confidence = consensus_confidence([claim])
    return claim


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return None
