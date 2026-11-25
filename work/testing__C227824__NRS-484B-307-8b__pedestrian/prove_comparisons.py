"""Audit five frozen comparison pairs against synthetic saved source packets."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_construction import ROOT


REPO = ROOT.parents[1]
SOURCE = REPO / ".runtime-work" / "c227824-saved-processing-v1"


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    target = ROOT / "comparisons"
    target.mkdir(exist_ok=True)
    rows = []
    for pair in plan["comparisons"]:
        ident = pair["comparison_id"]
        left, right = pair["case_ids"]
        output = target / (ident + "-diagnostic.json")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run([sys.executable, str(ROOT / "comparison_audit.py"),
                              "--left-attempt", str(SOURCE / left[len(ROOT.name) + 2:] / "attempt"),
                              "--right-attempt", str(SOURCE / right[len(ROOT.name) + 2:] / "attempt"),
                              "--comparison-id", ident, "--plan", str(ROOT / "case-plan.json"),
                              "--output", str(output)], cwd=REPO, env=env,
                             capture_output=True, text=True, timeout=120)
        if run.returncode:
            raise RuntimeError(ident + ": " + run.stdout + run.stderr)
        proof = json.loads(output.read_text())
        if proof.get("diagnostic_audit_passed") is not True or proof.get("physical_acceptance_claimed") is not False:
            raise ValueError("comparison proof overclaims or failed")
        rows.append({"comparison_id": ident, "case_ids": pair["case_ids"],
                     "diagnostic_passed": True,
                     "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    print(json.dumps({"format": "c227824-synthetic-comparison-summary",
                      "comparisons": rows, "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
