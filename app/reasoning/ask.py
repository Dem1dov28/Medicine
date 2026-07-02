"""Reasoning for /ask (RFC-0001 §4).

A question is answered ONLY from published Claims. The answer text is a
templated summary of the retrieved Claims — never a free-form LLM statement
without sources (RFC-0000: knowledge is explainable, every claim links to
first sources). Conflicts are surfaced, not hidden (§6).
"""

from __future__ import annotations

import re

from app.consensus import is_conflicting
from app.schemas import Answer, Claim, EffectDirection
from app.storage.repository import ClaimRepository

_STOPWORDS = {
    "the", "a", "an", "of", "for", "to", "is", "are", "does", "do", "and",
    "on", "in", "with", "what", "how", "effect", "effects",
}

_DIRECTION_WORD = {
    EffectDirection.increase: "increases",
    EffectDirection.decrease: "decreases",
    EffectDirection.no_effect: "has no clear effect on",
}


def _keywords(question: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9\-]+", question.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _describe(claim: Claim) -> str:
    verb = _DIRECTION_WORD[claim.effect.direction]
    magnitude = f" ({claim.effect.magnitude})" if claim.effect.magnitude else ""
    return (
        f"{claim.subject} {verb} {claim.outcome}{magnitude} "
        f"in {claim.population} "
        f"[evidence: {claim.evidence_level.value}, "
        f"confidence: {claim.consensus_confidence}]."
    )


def answer_question(question: str, repo: ClaimRepository) -> Answer:
    terms = _keywords(question)
    claims = repo.search(terms) if terms else []

    if not claims:
        return Answer(
            question=question,
            answer=(
                "No published claims match this question yet. v0 covers a narrow "
                "set of substances — the absence of an answer is itself a valid "
                "result."
            ),
            claims=[],
        )

    lines = [_describe(c) for c in claims]
    if is_conflicting(claims):
        lines.append(
            "Note: the retrieved claims disagree on the effect direction; "
            "both are shown and consensus confidence is reduced accordingly."
        )

    return Answer(question=question, answer=" ".join(lines), claims=claims)
