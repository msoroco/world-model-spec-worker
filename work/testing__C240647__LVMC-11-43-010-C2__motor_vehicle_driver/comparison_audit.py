"""Reopen both original attempts for one exact controlled roundabout comparison."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from analysis import measure

ASSIGNMENT="testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit(first,second,plan_path,comparison):
    plan=json.loads(Path(plan_path).read_text())
    target=next((row for row in plan["comparisons"] if row.get("comparison_id")==comparison),None)
    if target is None or len(target.get("case_ids",[]))!=2:
        raise ValueError("exact comparison missing")
    a,b=measure(first),measure(second)
    if [a["case_id"],b["case_id"]]!=target["case_ids"] or any(
            not case.startswith(ASSIGNMENT+"__") for case in target["case_ids"]):
        raise ValueError("comparison attempt identity differs")
    fixture=(Path(first)/"fixture-provenance.json").is_file()
    if fixture!=(Path(second)/"fixture-provenance.json").is_file():
        raise ValueError("comparison source profiles differ")
    expected_frames=9 if fixture else 900
    if a["source_frame_count"] != expected_frames or b["source_frame_count"] != expected_frames:
        raise ValueError("comparison original histories incomplete")
    cases={row["case_id"]:row for row in plan["cases"]}
    ca,cb=cases[a["case_id"]],cases[b["case_id"]]
    changed=[key for key in ("operator_intent_request","roundabout_lane_request","actual_exit_request")
             if ca[key]!=cb[key]]
    if not changed:
        raise ValueError("comparison has no exact controlled difference")
    single="single_right" in (ca["roundabout_lane_request"],cb["roundabout_lane_request"])
    if not single and a["map_id"]!=b["map_id"]:
        raise ValueError("comparison map identity changed")
    for key in ("vehicle_blueprint","entry_id","controller_sha256","weather_sha256","camera_plan_sha256"):
        if a["fixed_conditions"][key]!=b["fixed_conditions"][key]:
            raise ValueError("comparison fixed source changed: "+key)
    evidence={"first_map":sha(Path(first)/"map.json"),"first_history":sha(Path(first)/"history.json"),
              "second_map":sha(Path(second)/"map.json"),"second_history":sha(Path(second)/"history.json")}
    return {"format":"c240647-independent-controlled-comparison-v1",
            "comparison_id":comparison,"case_ids":target["case_ids"],
            "fixed_conditions":target["fixed_conditions"],
            "deliberate_differences":target["deliberate_differences"],
            "changed_control_fields":changed,"source_hashes":evidence,
            "measured":{"independent_operator_intents":[a["operator_intended_exit_role"],b["operator_intended_exit_role"]],
                        "occupied_circular_lanes":[a["occupied_ring_lane_ids"],b["occupied_ring_lane_ids"]],
                        "first_actual_connectors":[a["first_observed_exit_connector_id"],b["first_observed_exit_connector_id"]],
                        "right_lane_throughout":[a["all_circulating_frames_right_lane"],b["all_circulating_frames_right_lane"]]},
            "diagnostic_fixture":fixture,"physical_acceptance":False,
            "legal_lane_judgment":"unresolved"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--first",type=Path,required=True)
    parser.add_argument("--second",type=Path,required=True)
    parser.add_argument("--comparison",required=True)
    parser.add_argument("--comparison-id",required=True)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.comparison_id!=ASSIGNMENT+"__"+args.comparison:
        raise ValueError("exact comparison identity differs")
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    result=audit(args.first,args.second,args.plan,args.comparison)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")

if __name__ == "__main__":
    main()
