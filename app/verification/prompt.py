"""Prompt construction for grounded Claim verification (RFC-0002)."""

from __future__ import annotations

import json

from app.schemas import Claim

SYSTEM_PROMPT = (
    "You are a meticulous scientific fact-checker. You verify whether a "
    "structured medical Claim faithfully reflects a source text. You are NOT "
    "judging whether the claim is medically true in general — only whether each "
    "field is supported by a verbatim span in the provided source text.\n\n"
    "There are two tiers of fields:\n"
    "- CORE (subject, outcome, effect.direction): these MUST be supported. If any "
    "core field is missing or contradicted, the claim cannot pass.\n"
    "- CONTEXT (population, intervention, comparator): quote support if present, but "
    "a missing detail (e.g. exact dose) here should NOT by itself fail the claim.\n\n"
    "Rules:\n"
    "- For each field you assess, quote the exact supporting span, or mark it "
    "unsupported with source_quote=null.\n"
    "- verdict='pass' if ALL CORE fields are supported and nothing is contradicted.\n"
    "- verdict='fail' if any field (core or context) directly CONTRADICTS the source.\n"
    "- verdict='uncertain' only if a CORE field's support is missing/ambiguous.\n"
    "- Do not fail or hold solely because a CONTEXT detail is unstated.\n"
    "- You may propose downgrade flags (small_sample, high_heterogeneity) but you "
    "do NOT set evidence levels.\n"
    "Respond with ONLY a JSON object, no prose."
)

# Core fields that gate publication (RFC-0002, revised after calibration).
_REQUIRED_FIELDS_HINT = ["subject", "outcome", "effect.direction"]
_CONTEXT_FIELDS_HINT = ["population", "intervention", "comparator"]

_OUTPUT_SHAPE = {
    "verdict": "pass | fail | uncertain",
    "confidence": "0.0-1.0",
    "field_quotes": [
        {
            "field": "subject",
            "supported": True,
            "source_quote": "verbatim span or null",
            "confidence": 0.0,
        }
    ],
    "proposed_downgrades": ["small_sample", "high_heterogeneity"],
    "notes": "optional short string",
}


def build_user_prompt(claim: Claim, source_text: str) -> str:
    claim_json = json.dumps(
        {
            "subject": claim.subject,
            "population": claim.population,
            "intervention": claim.intervention.model_dump(),
            "comparator": claim.comparator,
            "outcome": claim.outcome,
            "effect": claim.effect.model_dump(mode="json"),
        },
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"CORE FIELDS (must be supported): {', '.join(_REQUIRED_FIELDS_HINT)}\n"
        f"CONTEXT FIELDS (support if present, do not fail on missing detail): "
        f"{', '.join(_CONTEXT_FIELDS_HINT)}\n\n"
        f"CLAIM:\n{claim_json}\n\n"
        f"SOURCE TEXT:\n\"\"\"\n{source_text}\n\"\"\"\n\n"
        f"Return JSON exactly in this shape:\n"
        f"{json.dumps(_OUTPUT_SHAPE, ensure_ascii=False, indent=2)}"
    )
