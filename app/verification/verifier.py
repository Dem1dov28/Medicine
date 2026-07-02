"""Ensemble verification + voting (RFC-0002).

Each configured model produces a ModelVerdict (via OpenRouter, or a deterministic
stub when no key is set). The voting rule turns the set of verdicts into a
decision: auto_verified (=> published), held, or rejected.
"""

from __future__ import annotations

import re
from statistics import fmean

from app.config import Settings, get_settings
from app.llm import LLMUnavailable, OpenRouterClient
from app.schemas import (
    Claim,
    ClaimStatus,
    EffectDirection,
    FieldQuote,
    ModelVerdict,
    VerdictType,
    VerificationRecord,
)
from app.verification.prompt import SYSTEM_PROMPT, build_user_prompt

# Core fields that MUST be grounded to publish (RFC-0002, revised after calibration).
REQUIRED_FIELDS = ["subject", "outcome", "effect.direction"]

_DIRECTION_KEYWORDS: dict[EffectDirection, tuple[str, ...]] = {
    EffectDirection.increase: ("increase", "improv", "higher", "greater", "gain", "rais"),
    EffectDirection.decrease: ("decrease", "reduc", "lower", "declin", "loss"),
    EffectDirection.no_effect: ("no effect", "no significant", "not associated", "no change"),
}


# --------------------------------------------------------------------------- #
# Stub verifier (no API key): deterministic, offline-friendly.
# --------------------------------------------------------------------------- #
def _sentence_containing(text: str, needle: str) -> str | None:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if needle.lower() in sentence.lower():
            return sentence.strip()
    return None


def _stub_verdict(model: str, claim: Claim, source_text: str) -> ModelVerdict:
    """Lenient grounding on subject + effect direction.

    This is explicitly a fake for offline/dev/tests — a real ensemble grounds
    every field via the LLM. It grounds truthfully on what it can check
    (subject presence, direction keywords) and is coarse on invented fields.
    """
    low = source_text.lower()
    subject_quote = _sentence_containing(source_text, claim.subject)
    subject_ok = subject_quote is not None

    direction_ok = any(k in low for k in _DIRECTION_KEYWORDS[claim.effect.direction])

    quotes = [
        FieldQuote(
            field="subject",
            supported=subject_ok,
            source_quote=subject_quote,
            confidence=0.9 if subject_ok else 0.2,
        ),
        FieldQuote(
            field="effect.direction",
            supported=direction_ok,
            source_quote=subject_quote if direction_ok else None,
            confidence=0.85 if direction_ok else 0.3,
        ),
    ]
    for field in ("population", "intervention", "outcome"):
        quotes.append(
            FieldQuote(field=field, supported=subject_ok, source_quote=None,
                       confidence=0.7 if subject_ok else 0.2)
        )

    if subject_ok and direction_ok:
        verdict, confidence = VerdictType.passed, 0.85
    elif not subject_ok:
        verdict, confidence = VerdictType.uncertain, 0.35
    else:
        verdict, confidence = VerdictType.uncertain, 0.5

    return ModelVerdict(
        model=model,
        verdict=verdict,
        confidence=confidence,
        field_quotes=quotes,
        proposed_downgrades=[],
        notes="stub verifier (no API key): lenient grounding on subject+direction",
    )


# --------------------------------------------------------------------------- #
# Real verifier (OpenRouter).
# --------------------------------------------------------------------------- #
_CORE_TOKENS = ("subject", "outcome", "direction")


def _is_core(field: str) -> bool:
    low = field.lower()
    return any(tok in low for tok in _CORE_TOKENS)


def _reconcile_verdict(verdict: ModelVerdict) -> ModelVerdict:
    """Enforce the core-only rule regardless of the model's holistic label.

    - A 'fail' (contradiction) is always trusted.
    - If every *core* field the model assessed is supported, an 'uncertain' is
      upgraded to 'pass' (it was likely held back by a context detail).
    - Otherwise the verdict is left unchanged.
    """
    if verdict.verdict == VerdictType.failed:
        return verdict

    core_quotes = [q for q in verdict.field_quotes if _is_core(q.field)]
    if core_quotes and all(q.supported for q in core_quotes):
        if verdict.verdict != VerdictType.passed:
            return verdict.model_copy(update={"verdict": VerdictType.passed})
    return verdict


def _llm_verdict(
    client: OpenRouterClient, model: str, claim: Claim, source_text: str
) -> ModelVerdict:
    raw = client.chat_json(
        model=model,
        system=SYSTEM_PROMPT,
        user=build_user_prompt(claim, source_text),
    )
    raw["model"] = model  # never trust the model to name itself
    return _reconcile_verdict(ModelVerdict.model_validate(raw))


# --------------------------------------------------------------------------- #
# Voting.
# --------------------------------------------------------------------------- #
def apply_voting(
    verdicts: list[ModelVerdict], threshold: float
) -> tuple[ClaimStatus, str, float]:
    """Turn a set of model verdicts into a decision (RFC-0002 voting rule)."""
    if not verdicts:
        return ClaimStatus.held, "no verdicts produced", 0.0

    mean_conf = round(fmean(v.confidence for v in verdicts), 2)
    kinds = {v.verdict for v in verdicts}

    if VerdictType.failed in kinds:
        return ClaimStatus.rejected, "at least one model returned fail", mean_conf

    if kinds == {VerdictType.passed} and mean_conf >= threshold:
        return (
            ClaimStatus.auto_verified,
            f"all models pass and mean confidence {mean_conf} >= {threshold}",
            mean_conf,
        )

    return (
        ClaimStatus.held,
        f"not unanimous pass or mean confidence {mean_conf} < {threshold}",
        mean_conf,
    )


def verify_claim(
    claim: Claim, source_text: str, settings: Settings | None = None
) -> VerificationRecord:
    settings = settings or get_settings()
    models = settings.verifier_models

    verdicts: list[ModelVerdict] = []
    if settings.llm_enabled:
        client = OpenRouterClient(settings)
        for model in models:
            try:
                verdicts.append(_llm_verdict(client, model, claim, source_text))
            except LLMUnavailable:
                # A failed provider call must not fake a pass; count as uncertain.
                verdicts.append(
                    ModelVerdict(
                        model=model,
                        verdict=VerdictType.uncertain,
                        confidence=0.0,
                        notes="provider call failed",
                    )
                )
    else:
        verdicts = [_stub_verdict(model, claim, source_text) for model in models]

    status, rule, mean_conf = apply_voting(verdicts, settings.verify_threshold)

    return VerificationRecord(
        models=models,
        per_model_verdicts=verdicts,
        decision_status=status,
        decision_rule=rule,
        mean_confidence=mean_conf,
    )
