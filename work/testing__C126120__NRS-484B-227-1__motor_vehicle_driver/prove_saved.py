"""Run the pinned Native-result path on a transient textual U-turn fixture."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not output_root.is_absolute() or not output_root.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(REPO/"runtime/scenario_pipeline"))

from analysis import build_report, saved_result
from case_builder import recording_description
from test_analysis import SavedAnalysisTests, write


def main():
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c126120-saved-") as tmp:
        root = Path(tmp)
        SavedAnalysisTests().build_attempt(root)
        description = recording_description()
        write(root/"construction.json",{"recording_description":description})
        write(root/"config.json",{"law_id":"NRS-484B-227-1","cell_id":"C126120",
            "actor":"motor_vehicle_driver","rate_hz":20,"duration_s":.25,
            "selected_case_id":"testing__C126120__NRS-484B-227-1__motor_vehicle_driver__diagnostic_only",
            "case":{"opening_id":"opening-1","multiple_movement_requested":False,
                    "recording_description":description},
            "physical_completion":{"criterion":"turn","motion_source":"ego-body-history.jsonl",
                "body_key":"body_vertices_xy_m","heading_key":"heading_deg",
                "context_sources":["median-context.json"],"turn_degrees":180,
                "turn_tolerance_deg":30,"minimum_progress_m":.25,"minimum_samples":3}})
        report = build_report(root)
        result = saved_result(root,report)
        if (result["physical_checks"]["maneuver"]["status"] != "met" or
                result["measured_values"]["legal_judgment"] != "unresolved" or
                result["physical_acceptance_claimed"] is not False):
            raise AssertionError("pinned saved U-turn result differs from diagnostic expectation")
        context = json.loads((root/"median-context.json").read_text())
        context["opening_id"] = "tampered"
        write(root/"median-context.json",context)
        try:
            build_report(root)
        except ValueError as exc:
            if "stale original Native source" not in str(exc): raise
        else:
            raise AssertionError("tampered original median context accepted")
        print(json.dumps({"pinned_saved_result_valid":True,"fixture_turn_met":True,
                          "tampered_original_rejected":True,"actual_capture_claimed":False}))


if __name__ == "__main__":
    main()
