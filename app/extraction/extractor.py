"""Extraction: article text -> a *draft* ClaimCreate (RFC-0001 §4).

The LLM only proposes structured fields; it never assigns an evidence level or
confidence (those come from the Evidence/Consensus engines). When no API key is
configured, a deterministic stub runs so the whole pipeline works offline and in
tests.
"""

from __future__ import annotations

import json
import re

from app.config import get_settings
from app.llm import LLMUnavailable, OpenRouterClient
from app.schemas import (
    ClaimCreate,
    Effect,
    EffectDirection,
    Intervention,
    Source,
    StudyType,
)

_EXTRACT_SYSTEM = (
    "You extract a single structured medical Claim from a study abstract or text. "
    "Return ONLY the fields present or clearly implied by the text. Do NOT invent "
    "effect sizes or study types. Do NOT assign an evidence level or confidence — "
    "those are computed downstream. Respond with ONLY a JSON object."
)

_EXTRACT_SHAPE = {
    "subject": "substance name",
    "population": "study population",
    "intervention": {"description": "what was given", "dose": "or null", "duration": "or null"},
    "comparator": "e.g. placebo, or null",
    "outcome": "measured outcome",
    "effect": {
        "direction": "increase | decrease | no_effect",
        "magnitude": "e.g. '+8%' or null",
        "ci_lower": "number or null",
        "ci_upper": "number or null",
        "p_value": "number or null",
    },
    "sources": [
        {
            "study_id": "short id",
            "pmid_or_doi": "identifier if present else 'unknown'",
            "study_type": "meta_analysis | systematic_review | rct | cohort | "
            "observational | case_series | expert_opinion",
            "year": "publication year as integer",
        }
    ],
}

_STUDY_TYPE_HINTS: list[tuple[str, StudyType]] = [
    ("meta-analysis", StudyType.meta_analysis),
    ("meta analysis", StudyType.meta_analysis),
    ("systematic review", StudyType.systematic_review),
    ("randomized", StudyType.rct),
    ("randomised", StudyType.rct),
    ("rct", StudyType.rct),
    ("cohort", StudyType.cohort),
    ("observational", StudyType.observational),
    ("case series", StudyType.case_series),
    ("expert opinion", StudyType.expert_opinion),
]

_INCREASE = ("increase", "improv", "higher", "greater", "gain")
_DECREASE = ("decrease", "reduc", "lower", "decline", "loss")


def _guess_study_type(text: str) -> StudyType:
    low = text.lower()
    for needle, study_type in _STUDY_TYPE_HINTS:
        if needle in low:
            return study_type
    return StudyType.observational


def _guess_direction(text: str) -> EffectDirection:
    low = text.lower()
    if any(w in low for w in _INCREASE):
        return EffectDirection.increase
    if any(w in low for w in _DECREASE):
        return EffectDirection.decrease
    return EffectDirection.no_effect


def _guess_magnitude(text: str) -> str | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?\s?%", text)
    return match.group(0).replace(" ", "") if match else None


def _guess_year(text: str) -> int:
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else 2000


def _stub_extract(text: str, subject: str | None) -> ClaimCreate:
    """Deterministic, dependency-free extraction for offline/dev/tests."""
    study_type = _guess_study_type(text)
    year = _guess_year(text)
    return ClaimCreate(
        subject=subject or "unknown",
        population="adults",
        intervention=Intervention(description=(subject or "intervention")),
        comparator="placebo",
        outcome="unspecified outcome",
        effect=Effect(
            direction=_guess_direction(text),
            magnitude=_guess_magnitude(text),
        ),
        sources=[
            Source(
                study_id="stub-1",
                pmid_or_doi="stub",
                study_type=study_type,
                year=year,
            )
        ],
    )


def _llm_extract(text: str, subject: str | None) -> ClaimCreate:
    settings = get_settings()
    client = OpenRouterClient(settings)
    subject_hint = f"\nThe substance of interest is: {subject}." if subject else ""
    user = (
        f"Extract the Claim as JSON in this shape:\n"
        f"{json.dumps(_EXTRACT_SHAPE, ensure_ascii=False, indent=2)}\n\n"
        f"TEXT:{subject_hint}\n\"\"\"\n{text}\n\"\"\""
    )
    raw = client.chat_json(settings.extractor_model, _EXTRACT_SYSTEM, user)
    if subject and not raw.get("subject"):
        raw["subject"] = subject
    return ClaimCreate.model_validate(raw)


def extract_claim(text: str, subject: str | None = None) -> ClaimCreate:
    settings = get_settings()
    if not settings.llm_enabled:
        # Stub mode: no external calls (RFC-0001 §1 — one provider, optional).
        return _stub_extract(text, subject)

    try:
        return _llm_extract(text, subject)
    except (LLMUnavailable, ValueError):
        # Never break the endpoint on a bad model response; fall back to stub.
        return _stub_extract(text, subject)
