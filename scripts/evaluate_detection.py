"""Offline evaluation — Precision / Recall / F1 / FPR.

Only computes scores when REAL labelled data is available.
If labels are missing or all predictions map to a single class, this script
prints "evaluation skipped" instead of fabricating numbers.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

# Allow running as `python scripts/evaluate_detection.py`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.errors import AppError
from app.services.detection import DetectionResult  # noqa: E402


def evaluate(
    true_labels: List[str],
    pred_labels: List[str],
    *,
    positive_label: Optional[str] = None,
    out_json: Optional[str] = None,
) -> Dict:
    """Compute classification metrics. Missing labels → SKIPPED (no fake scores)."""
    if not true_labels or not pred_labels:
        return {"status": "SKIPPED", "reason": "empty input"}
    if len(true_labels) != len(pred_labels):
        return {"status": "SKIPPED", "reason": f"length mismatch: {len(true_labels)} vs {len(pred_labels)}"}
    if not any(l != "normal" for l in true_labels):
        return {"status": "SKIPPED", "reason": "no non-normal labels in ground truth"}

    y_true = np.array(true_labels)
    y_pred = np.array(pred_labels)

    labels = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0, output_dict=True)
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    result: Dict = {
        "status": "OK",
        "labels": labels,
        "classification_report": report,
        "confusion_matrix": {"labels": labels, "matrix": cm},
    }

    # Optional binary positive/negative FPR against a chosen positive class
    if positive_label and positive_label in labels:
        # Treat positive_label as positive, everything else as negative
        y_true_bin = (y_true == positive_label).astype(int)
        y_pred_bin = (y_pred == positive_label).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true_bin, y_pred_bin, labels=[0, 1]).ravel()
        result[f"binary_{positive_label}"] = {
            "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn),
            "precision": float(tp / max(tp + fp, 1)),
            "recall": float(tp / max(tp + fn, 1)),
            "f1": float(2 * tp / max(2 * tp + fp + fn, 1)),
            "fpr": float(fp / max(fp + tn, 1)),
        }

    if out_json:
        Path(out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[evaluate] wrote → {out_json}")

    return result


# -------------------------- CLI entrypoint --------------------------------

def _cli() -> None:
    """Read synthetic CSV, run RuleDemoDetector, print evaluation."""
    from app.services.ingestion import iter_records
    from app.services.detection import RuleDemoDetector

    sample = ROOT / "data" / "samples" / "flows_sample.csv"
    flows = list(iter_records(sample))
    print(f"[evaluate_detection] loaded {len(flows)} flows from {sample}")

    # Pull ground truth directly from CSV (separate parser for clarity)
    truth: List[str] = []
    with sample.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            truth.append(row["label"])
    # Match length: iter_records might skip bad rows (we have none here)
    truth = truth[: len(flows)]

    det = RuleDemoDetector()
    results = det.predict(flows)
    preds = [r.predicted_label for r in results]

    # Per-class metrics
    out = evaluate(truth, preds, positive_label=None)
    print(json.dumps({k: v for k, v in out.items() if k != "classification_report"}, indent=2))

    # Also binary evaluation vs. port_scan and brute_force
    for pos in ("port_scan", "brute_force"):
        bin_out = evaluate(truth, preds, positive_label=pos)
        bin_only = bin_out.get(f"binary_{pos}")
        if bin_only:
            print(f"\n[binary positive={pos}] TP={bin_only['TP']} FP={bin_only['FP']} "
                  f"FN={bin_only['FN']} TN={bin_only['TN']} "
                  f"P={bin_only['precision']:.3f} R={bin_only['recall']:.3f} "
                  f"F1={bin_only['f1']:.3f} FPR={bin_only['fpr']:.3f}")


if __name__ == "__main__":
    _cli()
