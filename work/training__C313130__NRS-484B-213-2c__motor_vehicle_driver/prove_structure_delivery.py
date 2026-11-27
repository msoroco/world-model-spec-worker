"""Retain source-joined diagnostic acceptance and rejection for four cases."""

import json
from pathlib import Path

from structure_delivery_audit import check, ERROR


HERE = Path(__file__).resolve().parent


def run():
    cases = []
    for kind in ("bridge", "viaduct"):
        for side in ("right", "left"):
            case = HERE.name + "__" + kind + "_" + side
            diagnostic = check(case, True)
            try:
                check(case, False)
            except ValueError as exc:
                if str(exc) != ERROR:
                    raise
                rejected = str(exc)
            else:
                raise AssertionError("Original acceptance incorrectly claimed")
            cases.append({"case_id": case, "diagnostic": diagnostic,
                          "original_acceptance_rejected": rejected})
    return {"format": "worker-structure-delivery-diagnostic-audit",
            "cases": cases, "diagnostic_only": True,
            "physical_acceptance_claimed": False, "legal_verdict": None}


if __name__ == "__main__":
    report = run()
    (HERE / "structure-delivery-audit-proof.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": len(report["cases"]),
                      "original_acceptance_rejected": len(report["cases"])}))
