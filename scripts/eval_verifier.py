"""Evaluate the verification ensemble against a human-labelled gold set (RFC-0002).

Runs each gold Claim through the verifier and compares the decision
(published vs. held/rejected) to the human ``gold_publish`` label. Reports
precision/recall so the auto-publish threshold can be calibrated with evidence
rather than guessed.

Usage:
    python scripts/eval_verifier.py [path/to/goldset.json]

With no MKI_OPENROUTER_API_KEY set, this measures the deterministic stub; set the
key and MKI_VERIFIER_MODELS to measure real models.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import get_settings
from app.schemas import ClaimCreate, ClaimStatus
from app.services import build_draft_claim
from app.verification import verify_claim


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def main(path: Path) -> int:
    settings = get_settings()
    mode = "OpenRouter ensemble" if settings.llm_enabled else "STUB (no API key)"
    print(f"Verifier eval — mode: {mode}")
    print(f"Models: {settings.verifier_models}  threshold: {settings.verify_threshold}\n")

    entries = _load(path)

    # "publish" is the positive class.
    tp = fp = fn = tn = 0
    rows: list[tuple[str, bool, bool, str]] = []

    for entry in entries:
        claim = build_draft_claim(ClaimCreate.model_validate(entry["claim"]))
        record = verify_claim(claim, entry["source_text"], settings)
        predicted = record.decision_status == ClaimStatus.auto_verified
        gold = bool(entry["gold_publish"])

        if predicted and gold:
            tp += 1
        elif predicted and not gold:
            fp += 1
        elif not predicted and gold:
            fn += 1
        else:
            tn += 1

        rows.append((entry["id"], gold, predicted, record.decision_status.value))

    print(f"{'id':<28} {'gold':<7} {'pred':<7} decision")
    print("-" * 60)
    for cid, gold, pred, decision in rows:
        mark = "" if gold == pred else "  <-- MISMATCH"
        print(f"{cid:<28} {str(gold):<7} {str(pred):<7} {decision}{mark}")

    p_pub, r_pub, f_pub = _prf(tp, fp, fn)
    # "block" (held/rejected) as positive: TP=tn, FP=fn, FN=fp
    p_blk, r_blk, f_blk = _prf(tn, fn, fp)
    accuracy = round((tp + tn) / len(entries), 3) if entries else 0.0

    print("\nConfusion (positive = publish):")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"\npublish  precision={p_pub}  recall={r_pub}  f1={f_pub}")
    print(f"block    precision={p_blk}  recall={r_blk}  f1={f_blk}")
    print(f"accuracy={accuracy}")

    # RFC-0002 target: never publish an unfaithful claim (no false publishes).
    if fp:
        print(f"\nWARNING: {fp} false publish(es) — unfaithful claims were published.")
    return 0


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "goldset.json"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    raise SystemExit(main(target))
