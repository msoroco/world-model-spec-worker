"""Prove production delivery and comparison commands reject diagnostic sources."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from build_construction import ROOT


REPO = ROOT.parents[1]
SAVED = REPO / ".runtime-work" / "c227824-saved-processing-v1"
PRIVATE = REPO / ".runtime-work" / "c227824-production-audit-negative"


def rejected(args, output):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    run = subprocess.run([sys.executable, *map(str, args)], cwd=REPO, env=env,
                         capture_output=True, text=True, timeout=120)
    if run.returncode == 0 or output.exists():
        raise ValueError("diagnostic attempt was accepted by production audit")
    expected = "missing or unsafe sealed source: capture-seal.json"
    if expected not in run.stderr:
        raise ValueError("production audit failed for an unexpected reason: " + run.stderr[-500:])
    return {"exit_code": run.returncode, "expected_error": expected,
            "output_absent": True}


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        output = PRIVATE / (suffix + "-delivery.json")
        output.unlink(missing_ok=True)
        row = rejected([ROOT / "delivery_audit.py", "--attempt",
                        SAVED / suffix / "attempt", "--case", case_id,
                        "--output", output], output)
        cases.append({"case_id": case_id, **row})
    comparisons = []
    for pair in plan["comparisons"]:
        ident = pair["comparison_id"]
        left, right = [case_id[len(ROOT.name) + 2:] for case_id in pair["case_ids"]]
        output = PRIVATE / (ident + "-comparison.json")
        output.unlink(missing_ok=True)
        row = rejected([ROOT / "comparison_delivery.py", "--left-attempt",
                        SAVED / left / "attempt", "--right-attempt",
                        SAVED / right / "attempt", "--comparison-id", ident,
                        "--output", output], output)
        comparisons.append({"comparison_id": ident, **row})
    print(json.dumps({"format": "c227824-production-audit-negative-proof",
                      "cases": cases, "comparisons": comparisons,
                      "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
