"""Pydantic contract for the Claim model (RFC-0001 §2).

These models are the single source of truth for the API. SQLAlchemy storage
serialises to/from these types, and the API returns them directly so that the
OpenAPI schema always matches what callers receive.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EffectDirection(str, Enum):
    increase = "increase"
    decrease = "decrease"
    no_effect = "no_effect"


class EvidenceLevel(str, Enum):
    high = "high"
    moderate = "moderate"
    low = "low"
    very_low = "very_low"


class StudyType(str, Enum):
    """Study designs recognised by the Evidence Engine (RFC-0001 §3)."""

    meta_analysis = "meta_analysis"
    systematic_review = "systematic_review"
    rct = "rct"
    cohort = "cohort"
    observational = "observational"
    case_series = "case_series"
    expert_opinion = "expert_opinion"


class ClaimStatus(str, Enum):
    """Claim lifecycle (RFC-0002 extends RFC-0001 §5).

    draft -> auto_verified -> published is the happy path. ``held`` and
    ``rejected`` are terminal branches produced by the verification ensemble when
    it is unsure or finds a contradiction; neither is visible to users.
    """

    draft = "draft"
    auto_verified = "auto_verified"
    published = "published"
    held = "held"
    rejected = "rejected"
    # Retained for a possible future manual override; unused in the happy path.
    verified = "verified"


class VerdictType(str, Enum):
    """A single model's verdict on a draft Claim (RFC-0002)."""

    passed = "pass"
    failed = "fail"
    uncertain = "uncertain"


class DowngradeFlag(str, Enum):
    """Downgrade signals the verifier may *propose*; the Evidence Engine applies them."""

    small_sample = "small_sample"
    high_heterogeneity = "high_heterogeneity"


class Intervention(BaseModel):
    description: str
    dose: str | None = None
    duration: str | None = None


class Effect(BaseModel):
    direction: EffectDirection
    magnitude: str | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None


class Source(BaseModel):
    study_id: str
    pmid_or_doi: str
    study_type: StudyType
    year: int


class FieldQuote(BaseModel):
    """Per-field grounding: a claim field must be backed by a verbatim source span."""

    field: str
    supported: bool
    source_quote: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ModelVerdict(BaseModel):
    """One ensemble member's assessment of a draft Claim (RFC-0002)."""

    model: str
    verdict: VerdictType
    confidence: float = Field(ge=0.0, le=1.0)
    field_quotes: list[FieldQuote] = Field(default_factory=list)
    proposed_downgrades: list[DowngradeFlag] = Field(default_factory=list)
    notes: str | None = None


class VerificationRecord(BaseModel):
    """Auditable provenance of the verification decision (RFC-0002)."""

    models: list[str]
    per_model_verdicts: list[ModelVerdict]
    decision_status: "ClaimStatus"
    decision_rule: str
    mean_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)


class ClaimBase(BaseModel):
    subject: str
    population: str
    intervention: Intervention
    comparator: str | None = None
    outcome: str
    effect: Effect
    sources: list[Source] = Field(min_length=1)


class ClaimCreate(ClaimBase):
    """Payload used to create a draft Claim.

    ``evidence_level`` and ``consensus_confidence`` are intentionally absent:
    they are computed by the Evidence/Consensus engines, never supplied by a
    caller or the LLM (RFC-0000 first principle: LLM is not an authority).
    """


class Claim(ClaimBase):
    id: UUID = Field(default_factory=uuid4)

    # Derived by the Evidence Engine, not by the LLM or the caller.
    evidence_level: EvidenceLevel
    consensus_confidence: float = Field(ge=0.0, le=1.0)

    status: ClaimStatus = ClaimStatus.draft
    # Structured origin of the decision: "llm:ensemble" or "human:<id>" (RFC-0002).
    verified_by: str | None = None
    verification: VerificationRecord | None = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _verified_requires_verifier(self) -> "Claim":
        # RFC-0001 §2/§5: anything past draft must record who decided it.
        if self.status != ClaimStatus.draft and not self.verified_by:
            raise ValueError("verified_by is required when status is not 'draft'")
        return self


class ExtractRequest(BaseModel):
    text: str
    subject: str | None = None


class SubstanceSummary(BaseModel):
    subject: str
    published_claims: int
    outcomes: list["OutcomeConsensus"]


class OutcomeConsensus(BaseModel):
    outcome: str
    evidence_level: EvidenceLevel
    consensus_confidence: float
    conflicting: bool
    claims: list[Claim]


class Answer(BaseModel):
    question: str
    answer: str
    claims: list[Claim]


VerificationRecord.model_rebuild()
Claim.model_rebuild()
SubstanceSummary.model_rebuild()
