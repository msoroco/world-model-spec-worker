"""Check exact intent and proof bindings with the pinned delivery validator."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
if not output.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def main() -> None:
    draft = json.loads((ROOT / "delivery-acceptance.partial.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if (draft.get("diagnostic_only") is not True or
            {entry["case_id"] for entry in draft["cases"]} !=
            {entry["case_id"] for entry in plan["cases"]} or
            {entry["comparison_id"] for entry in draft["comparisons"]} !=
            {entry["comparison_id"] for entry in plan["comparisons"]}):
        raise ValueError("partial acceptance coverage or provenance differs")
    for receipt in draft["cases"]:
        validate_case(ROOT, {"case_id": receipt["case_id"],
                             "delivery_acceptance": receipt}, {"full-test"})
    print("six exact pinned delivery contracts and four comparison identities pass; diagnostic only")


if __name__ == "__main__":
    main()
