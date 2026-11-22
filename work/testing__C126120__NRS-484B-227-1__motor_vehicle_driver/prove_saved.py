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

from analysis import build_report, saved_result, sha
from case_builder import recording_description
from test_analysis import SavedAnalysisTests, write, lines


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
                result["diagnostic_fixture"] is not True or
                result["physical_acceptance_claimed"] is not False):
            raise AssertionError("pinned saved U-turn result differs from diagnostic expectation")
        context = json.loads((root/"median-context.json").read_text())
        context["opening_id"] = "tampered"
        write(root/"median-context.json",context)
        try:
            build_report(root)
        except ValueError as exc:
            if "stale provenance-bound source" not in str(exc): raise
        else:
            raise AssertionError("tampered original median context accepted")
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c126120-closed-") as tmp:
        root = Path(tmp)
        SavedAnalysisTests().build_attempt(root)
        body = [{"frame":i,"time_s":i/20,"actor_id":7,
                 "body_vertices_xy_m":[[1.8,y-.2],[2.2,y-.2],[2.2,y+.2],[1.8,y+.2]],
                 "heading_deg":90,"velocity_xy_mps":[0,1]}
                for i,y in enumerate((-2,-1.8,-1.5,-1.25))]
        lines(root/"ego-body-history.jsonl",body)
        lines(root/"controller-history.jsonl",[
            {"frame":r["frame"],"time_s":r["time_s"],"ego_actor_id":7,
             "next_tick_request":{}} for r in body])
        lines(root/"video_frames.jsonl",[
            {"carla_frame":r["frame"],"video_frame":i,"time_s":r["time_s"]}
            for i,r in enumerate(body)])
        lines(root/"trace.jsonl",[{"frame":r["frame"]} for r in body])
        acquisition=json.loads((root/"acquisition.json").read_text())
        for name in ("ego-body-history.jsonl","controller-history.jsonl",
                     "video_frames.jsonl","trace.jsonl"):
            acquisition[name]["sha256"]=sha(root/name)
        write(root/"acquisition.json",acquisition)
        description=recording_description()
        write(root/"construction.json",{"recording_description":description})
        write(root/"config.json",{"law_id":"NRS-484B-227-1","cell_id":"C126120",
            "actor":"motor_vehicle_driver","rate_hz":20,"duration_s":.2,
            "selected_case_id":"testing__C126120__NRS-484B-227-1__motor_vehicle_driver__closed_divider",
            "case":{"physical_target":"closed_divider_approach",
                    "multiple_movement_requested":False,
                    "recording_description":description},
            "physical_completion":{"criterion":"travel_progress",
                "motion_source":"ego-body-history.jsonl","body_key":"body_vertices_xy_m",
                "context_sources":["median-context.json"],"direction_xy":[0,1],
                "minimum_progress_m":.5,"minimum_samples":3}})
        report=build_report(root)
        result=saved_result(root,report)
        if (result["physical_checks"]["maneuver"]["status"]!="met" or
                not all(item["matched"] for item in result["target_checks"]) or
                result["measured_values"]["engineering_crossing_observed"] or
                result["diagnostic_fixture"] is not True):
            raise AssertionError("pinned closed-divider result differs from diagnostic expectation")
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c126120-wrong-") as tmp:
        root=Path(tmp)
        SavedAnalysisTests().build_attempt(root)
        reviewed=json.loads((root/"reviewed-median-context.json").read_text())
        reviewed["context"]["destination_right_roadway_bounds_xy_m"]=[-4,2,4,4]
        reviewed["context"]["opposite_non_right_roadway_bounds_xy_m"]=[-4,1.2,4,2]
        write(root/"reviewed-median-context.json",reviewed)
        context=json.loads((root/"median-context.json").read_text())
        context.update(reviewed["context"])
        context["reviewed_context_sha256"]=sha(root/"reviewed-median-context.json")
        write(root/"median-context.json",context)
        provenance=json.loads((root/"acquisition-provenance.json").read_text())
        provenance["reviewed_context_sha256"]=context["reviewed_context_sha256"]
        write(root/"acquisition-provenance.json",provenance)
        body=[{"frame":i,"time_s":i/20,"actor_id":7,
               "body_vertices_xy_m":[[-.2,y-.2],[.2,y-.2],[.2,y+.2],[-.2,y+.2]],
               "heading_deg":90,"velocity_xy_mps":[0,1]}
              for i,y in enumerate((-2,-1.5,-.5,0,1,1.5))]
        lines(root/"ego-body-history.jsonl",body)
        lines(root/"controller-history.jsonl",[
            {"frame":r["frame"],"time_s":r["time_s"],"ego_actor_id":7,
             "next_tick_request":{}} for r in body])
        lines(root/"video_frames.jsonl",[
            {"carla_frame":r["frame"],"video_frame":i,"time_s":r["time_s"]}
            for i,r in enumerate(body)])
        lines(root/"trace.jsonl",[{"frame":r["frame"]} for r in body])
        acquisition=json.loads((root/"acquisition.json").read_text())
        for name in ("reviewed-median-context.json","median-context.json",
                     "ego-body-history.jsonl","controller-history.jsonl",
                     "video_frames.jsonl","trace.jsonl"):
            acquisition[name]["sha256"]=sha(root/name)
        write(root/"acquisition.json",acquisition)
        description=recording_description()
        write(root/"construction.json",{"recording_description":description})
        write(root/"config.json",{"law_id":"NRS-484B-227-1","cell_id":"C126120",
            "actor":"motor_vehicle_driver","rate_hz":20,"duration_s":.3,
            "selected_case_id":"testing__C126120__NRS-484B-227-1__motor_vehicle_driver__wrong_roadway",
            "case":{"physical_target":"non_right_roadway",
                    "multiple_movement_requested":False,
                    "recording_description":description},
            "physical_completion":{"criterion":"travel_progress",
                "motion_source":"ego-body-history.jsonl","body_key":"body_vertices_xy_m",
                "context_sources":["median-context.json"],"direction_xy":[0,1],
                "minimum_progress_m":2,"minimum_samples":3}})
        result=saved_result(root,build_report(root))
        if (result["physical_checks"]["maneuver"]["status"]!="met" or
                not all(item["matched"] for item in result["target_checks"]) or
                not result["measured_values"]["non_right_roadway_final_occupancy"] or
                result["measured_values"]["destination_right_roadway_departure_observed"] or
                result["diagnostic_fixture"] is not True):
            raise AssertionError("pinned wrong-roadway result differs from diagnostic expectation")
    with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",prefix="c126120-no-turn-") as tmp:
        root=Path(tmp)
        SavedAnalysisTests().build_attempt(root)
        body=[{"frame":i,"time_s":i/20,"actor_id":7,
               "body_vertices_xy_m":[[x-.2,-2.2],[x+.2,-2.2],
                                     [x+.2,-1.8],[x-.2,-1.8]],
               "heading_deg":0,"velocity_xy_mps":[1,0]}
              for i,x in enumerate((-3,-2,-1,0,1))]
        lines(root/"ego-body-history.jsonl",body)
        lines(root/"controller-history.jsonl",[
            {"frame":r["frame"],"time_s":r["time_s"],"ego_actor_id":7,
             "next_tick_request":{}} for r in body])
        lines(root/"video_frames.jsonl",[
            {"carla_frame":r["frame"],"video_frame":i,"time_s":r["time_s"]}
            for i,r in enumerate(body)])
        lines(root/"trace.jsonl",[{"frame":r["frame"]} for r in body])
        acquisition=json.loads((root/"acquisition.json").read_text())
        for name in ("ego-body-history.jsonl","controller-history.jsonl",
                     "video_frames.jsonl","trace.jsonl"):
            acquisition[name]["sha256"]=sha(root/name)
        write(root/"acquisition.json",acquisition)
        description=recording_description()
        write(root/"construction.json",{"recording_description":description})
        write(root/"config.json",{"law_id":"NRS-484B-227-1","cell_id":"C126120",
            "actor":"motor_vehicle_driver","rate_hz":20,"duration_s":.25,
            "selected_case_id":"testing__C126120__NRS-484B-227-1__motor_vehicle_driver__right_roadway_no_turn",
            "case":{"physical_target":"source_right_roadway_continuation",
                    "multiple_movement_requested":False,
                    "recording_description":description},
            "physical_completion":{"criterion":"travel_progress",
                "motion_source":"ego-body-history.jsonl","body_key":"body_vertices_xy_m",
                "context_sources":["median-context.json"],"direction_xy":[1,0],
                "minimum_progress_m":2,"minimum_samples":3}})
        result=saved_result(root,build_report(root))
        if (result["physical_checks"]["maneuver"]["status"]!="met" or
                not all(item["matched"] for item in result["target_checks"]) or
                not result["measured_values"]["source_right_roadway_all_frames"] or
                result["measured_values"]["opening_contact_frames"] or
                result["diagnostic_fixture"] is not True):
            raise AssertionError("pinned no-turn result differs from diagnostic expectation")
        print(json.dumps({"pinned_saved_result_valid":True,"fixture_turn_met":True,
                          "closed_approach_fixture_met":True,
                          "wrong_roadway_fixture_met":True,
                          "right_roadway_no_turn_fixture_met":True,
                          "tampered_original_rejected":True,"actual_capture_claimed":False}))


if __name__ == "__main__":
    main()
