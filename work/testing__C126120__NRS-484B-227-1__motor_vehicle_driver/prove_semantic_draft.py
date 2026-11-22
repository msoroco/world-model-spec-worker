"""Validate pinned semantic stages against seven source-exact draft constructions."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
output_root=Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()
if not output_root.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0,str(REPO/"runtime/scenario_pipeline"))

from worker_exchange.semantic_delivery import validate


def main():
    assignment=json.loads((REPO/"inputs"/ROOT.name/"assignment.json").read_text())
    plan=json.loads((ROOT/"case-plan.json").read_text())
    manifest={"cases":[{"case_id":c["case_id"],
                        "construction":"cases/"+c["case_id"].rsplit("__",1)[-1]+"/construction.json"}
                       for c in plan["cases"]]}
    stage=validate(ROOT,assignment,manifest)
    print(json.dumps({"canonical_semantic_stages_valid":True,
                      "selected_case_count":stage["selected_cases"],
                      "per_case_construction_drafts_bound":True,
                      "delivery_ready_claimed":False}))


if __name__=="__main__":
    main()
