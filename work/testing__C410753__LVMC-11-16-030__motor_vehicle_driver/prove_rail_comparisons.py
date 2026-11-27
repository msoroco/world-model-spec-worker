"""Exercise each planned railway contrast on source-complete CPU recordings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from copy import deepcopy

from rail_comparison_audit import audit_comparison
from rail_diagnostic_measurement import verify_diagnostic
from rail_saved_measurement import _source

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    saved = {}
    for case in plan["cases"]:
        case_id = case["case_id"]
        key = case_id.removeprefix(HERE.name + "__")
        attempt = REPO / (".runtime-work/c410753-compat-first-v8" if key == "obscured_14mph"
                          else ".runtime-work/c410753-compat-" + key + "-v8")
        receipt = json.loads((attempt / "native-rail-receipt.json").read_text())
        packet = json.loads(_source(attempt, receipt["packet"]).read_text())
        saved[case_id] = verify_diagnostic(attempt, receipt, packet, case_id)
    for comparison in plan["comparisons"]:
        identifier = comparison["comparison_id"]
        selected = {case: saved[case] for case in comparison["case_ids"]}
        positive = audit_comparison(plan, identifier, selected)
        changed = deepcopy(selected)
        first = comparison["case_ids"][0]
        changed[first]["observation"]["speed_boundary_relation_observed"] = "not_observed"
        try:
            audit_comparison(plan, identifier, changed)
        except ValueError as error:
            if "planned railway contrast not observed" not in str(error):
                raise
            negative = str(error)
        else:
            raise ValueError("altered railway contrast was accepted")
        result = {"format": "worker-rail-comparison-cpu-proof",
                  "comparison_id": identifier,
                  "source_complete_diagnostic_cases": comparison["case_ids"],
                  "positive": positive, "negative_rejection": negative,
                  "diagnostic_only": True, "physical_completion_confirmed": False,
                  "legal_conclusion": None}
        path = HERE / ("comparison-" + identifier + "-receipt.json")
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(identifier, "passed", hashlib.sha256(path.read_bytes()).hexdigest(),
              flush=True)


if __name__ == "__main__":
    main()
