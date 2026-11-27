"""Retain two positive and two swapped-contrast negative diagnostic proofs."""

import json
from pathlib import Path

from structure_comparison_audit import check


def run():
    comparisons = []
    for kind in ("bridge", "viaduct"):
        positive = check(kind)
        try:
            check(kind, swap=True)
        except ValueError as exc:
            negative = str(exc)
        else:
            raise AssertionError("Swapped structure contrast was accepted")
        comparisons.append({"kind": kind, "positive": positive,
                            "negative_swap_rejected": negative})
    return {"format": "worker-structure-comparison-audit",
            "diagnostic_only": True, "comparisons": comparisons,
            "physical_acceptance_claimed": False, "legal_verdict": None}


if __name__ == "__main__":
    report = run()
    path = Path(__file__).resolve().parent / "structure-comparison-audit-proof.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"comparisons": len(report["comparisons"]),
                      "negative_swaps_rejected": 2}))
