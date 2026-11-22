"""Exercise the pinned selected-requirement contract on textual sources."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
output_root=Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT","")).resolve()
if not output_root.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path[0:0]=[str(ROOT),str(ROOT/"tests"),str(REPO/"runtime/scenario_pipeline")]

from analysis import build_report
from test_analysis import SavedAnalysisTests
from worker_exchange.measurement_contract import validate,verify_report


def main():
    plan=json.loads((ROOT/"case-plan.json").read_text())
    contract=json.loads((ROOT/"measurement-contract.json").read_text())
    case_id=plan["cases"][0]["case_id"]
    validate(contract,plan["requirement_dispositions"],(ROOT/"analysis.py").read_text(),case_id)
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c126120-measure-") as temp:
        folder=Path(temp)
        SavedAnalysisTests().build_attempt(folder)
        report=build_report(folder)
        measurements=verify_report(contract,report,folder)
        if not measurements["median_uturn_measurement"]["value"]["engineering_crossing_observed"]:
            raise AssertionError("diagnostic opening geometry was not measured")
        (folder/contract["negative"]["remove"][0]).unlink()
        try:
            build_report(folder)
        except ValueError as exc:
            if contract["negative"]["error_contains"] not in str(exc): raise
        else:
            raise AssertionError("missing original source was accepted")
    print(json.dumps({"selected_requirement_contract_valid":True,
                      "source_hash_join_valid":True,
                      "negative_missing_source_rejected":True,
                      "actual_capture_claimed":False}))


if __name__=="__main__": main()
