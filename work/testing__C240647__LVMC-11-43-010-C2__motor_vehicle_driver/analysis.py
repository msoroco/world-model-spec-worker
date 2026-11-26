"""Saved-only original operator-intent, circulating lane, and exit measurement."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from roundabout import load_sealed_json, verify_original_history, verify_topology

VIEWS=("overview","approach","reference_corner","driver_reference")

def required(root,name):
    path=Path(root)/name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: "+name)
    return path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def measure(attempt):
    root=Path(attempt)
    config=json.loads(required(root,"config.json").read_text())
    construction=json.loads(required(root,"construction.json").read_text())
    case_id=config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("selected exact construction differs")
    inventory=json.loads(required(root,"inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native source inventory differs")
    refs=inventory.get("sources",{})
    if set(refs) != {"map","history"}:
        raise ValueError("original map and actor history sources required")
    for name in refs:
        if refs[name].get("path") != name+".json":
            raise ValueError("original source path mismatch")
    source=load_sealed_json(required(root,"map.json"),refs["map"]["sha256"])
    history=load_sealed_json(required(root,"history.json"),refs["history"]["sha256"])
    plan=json.loads(required(root,"case-plan.json").read_text())
    case=next((row for row in plan["cases"] if row["case_id"] == case_id),None)
    if case is None:
        raise ValueError("selected exact case absent")
    topology=verify_topology(source,case)
    expected=9 if (root/"fixture-provenance.json").is_file() else 900
    observed=verify_original_history(history,topology,case_id,expected_frames=expected)
    if inventory.get("frame_count") != expected or inventory.get("camera_views") != list(VIEWS):
        raise ValueError("original four-view frame inventory incomplete")
    return observed

def measure_intent(attempt):
    observed=measure(attempt)
    return {key:observed[key] for key in ("operator_intended_exit_role","actor_id","map_id")}

def measure_lane_use(attempt):
    observed=measure(attempt)
    return {key:observed[key] for key in ("right_lane_id","occupied_ring_lane_ids",
        "all_circulating_frames_right_lane","last_circulating_lane_id","source_frame_count")}

def measure_actual_exit(attempt):
    observed=measure(attempt)
    return {key:observed[key] for key in ("first_observed_exit_connector_id",
        "right_exit_connector_id","right_exit_observed","source_frame_count")}

def analyze(attempt,output):
    root=Path(attempt)
    observed=measure(root)
    construction=json.loads(required(root,"construction.json").read_text())
    trace=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines()]
    expected=9 if (root/"fixture-provenance.json").is_file() else 900
    if len(trace) != expected:
        raise ValueError("original trace frame count incomplete")
    values={"intent":measure_intent(root),"lane_use":measure_lane_use(root),
            "actual_exit":measure_actual_exit(root)}
    hashes={name:sha(required(root,name)) for name in ("map.json","history.json")}
    report={"format":"worker-analysis-report","case_id":observed["case_id"],
            "measurements":{key:{"method":"measure_"+key,"value":value,"sources":hashes}
                            for key,value in values.items()},
            "diagnostic_fixture":(root/"fixture-provenance.json").is_file(),
            "legal_verdict_claimed":False,
            "limitations":["Intent is independently sourced; motion does not establish the intended exit.",
                           "CPU fixtures do not establish physical Native success or a legal right-lane conclusion."]}
    recording=construction["recording_description"]
    channels=root/"channels"
    channels.mkdir(exist_ok=False)
    evidence=[]
    channel_values={
        "original_roundabout_topology":{"source_sha256":hashes["map.json"],"map_id":observed["map_id"]},
        "independent_operator_intent":{"source_sha256":hashes["history.json"],"role":observed["operator_intended_exit_role"]},
        "original_ring_lane_history":{"source_sha256":hashes["history.json"],"lanes":observed["occupied_ring_lane_ids"]},
        "actual_exit_connector":{"source_sha256":hashes["history.json"],"connector":observed["first_observed_exit_connector_id"]},
        "original_four_camera_pixels":{"source_sha256":sha(required(root,"video_frames.jsonl")),"view_count":4}}
    for channel in recording["channels"]:
        name=channel["name"]
        if name not in channel_values:
            raise ValueError("unexpected original capture channel: "+name)
        target=channels/(name+".jsonl")
        target.write_text("".join(json.dumps({"time_s":row["time_s"],"value":channel_values[name]})+"\n" for row in trace))
        evidence.append({"name":name,"unit":channel["unit"],"reference":str(target.relative_to(root))})
    context=channels/"reviewed_roundabout_map.json"
    context.write_text(json.dumps({"reviewed_roundabout_map":{"map_sha256":hashes["map.json"],
                                          "legal_judgment":"unresolved"}})+"\n")
    evidence.append({"name":"reviewed_roundabout_map","unit":"source",
                     "reference":str(context.relative_to(root))})
    result={"case_id":observed["case_id"],"measured_values":values,
            "target_checks":[{"target":"original intent, circular lane and actual connector",
                "requested":"source-bound measurement without legal cutoff","measured":values,
                "method":"measure_intent/measure_lane_use/measure_actual_exit","tolerance":0,
                "matched":True,"physical_cause_confirmed":False,"cause_evidence":hashes}],
            "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
            "termination_reason":"Saved original review pending","physical_failure_flags":[],
            "trace_reference":"trace.jsonl","video_references":[name+".mkv" for name in VIEWS],
            "video_frame_map_reference":"video_frames.jsonl","recording_description":recording,
            "recording_evidence":evidence,"realized_observables":{},"legal_judgment":None,
            "physical_acceptance_claimed":False}
    (root/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    Path(output).write_text(json.dumps(report,indent=2)+"\n")
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(analyze(args.attempt,args.output)["case_id"])

if __name__ == "__main__":
    main()
