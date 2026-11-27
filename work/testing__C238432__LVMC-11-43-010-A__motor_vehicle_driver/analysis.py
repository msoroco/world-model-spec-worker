"""Saved-only original roundabout direction finalizer, without a legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from direction import CASE_DIRECTIONS, load_source, measure_history

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def required(root, name):
    path = Path(root)/name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(root):
    root=Path(root)
    config=json.loads(required(root,"config.json").read_text())
    case_id=config["selected_case_id"]
    if case_id not in CASE_DIRECTIONS:
        raise ValueError("wrong exact direction case")
    inventory=json.loads(required(root,"inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native":
        raise ValueError("original Native inventory identity mismatch")
    refs=inventory.get("sources",{})
    if set(refs) < {"map","history"}:
        raise ValueError("original map and history references missing")
    for name in ("map","history"):
        if refs[name].get("path") != name+".json" or sha(required(root,name+".json")) != refs[name].get("sha256"):
            raise ValueError("original Native source hash mismatch: "+name)
    packet=load_source(required(root,"map.json"),refs["map"]["sha256"],case_id)
    history=json.loads(required(root,"history.json").read_text())
    expected=9 if (root/"fixture-provenance.json").is_file() else 900
    if inventory.get("frame_count") != expected or inventory.get("camera_views") != list(VIEWS):
        raise ValueError("source-profile four-view inventory incomplete")
    observed=measure_history(packet,history,case_id,expected_frames=expected)
    frame_map=[json.loads(line) for line in required(root,"video_frames.jsonl").read_text().splitlines()]
    trace=[json.loads(line) for line in required(root,"trace.jsonl").read_text().splitlines()]
    if len(frame_map) != expected or len(trace) != expected:
        raise ValueError("saved original frame joins incomplete")
    for index,(mapping,row) in enumerate(zip(frame_map,trace)):
        original=history["frames"][index]
        position=row.get("position_m",[])
        if (mapping.get("video_frame") != index or
                mapping.get("native_frame") != row.get("frame") or
                row.get("frame") != original.get("frame") or
                row.get("actor_id",history["actor_id"]) != history["actor_id"] or
                len(position)<2 or
                abs(position[0]-original["x"])>.001 or
                abs(position[1]-original["y"])>.001):
            raise ValueError("saved original frame join differs")
    for name in VIEWS:
        required(root,name+".mkv")
    return observed,trace,packet


def measure_roundabout(root):
    observed,_,packet=measure(root)
    return {"map_name":observed["map_name"],"jurisdiction":packet["jurisdiction"],
            "central_island":bool(packet["central_island"]),
            "circulatory_lane_ids":packet["circulatory_roadway"]["lane_ids"]}


def measure_operator(root):
    observed,_,_=measure(root)
    return {"actor_id":observed["actor_id"],"source_frames":observed["source_frames"]}


def measure_direction(root):
    observed,_,_=measure(root)
    return {"ring_frames":observed["ring_frames"],
            "signed_arc_rad":observed["signed_arc_rad"],
            "observed_direction":observed["observed_direction"],
            "requested_direction":observed["requested_direction"]}


def analyze(root, output):
    root=Path(root)
    observed,trace,packet=measure(root)
    config=json.loads(required(root,"config.json").read_text())
    recording=config["case"]["recording_description"]
    hashes={name:sha(required(root,name)) for name in ("map.json","history.json","video_frames.jsonl")}
    report={"format":"worker-analysis-report","case_id":observed["case_id"],
            "measurements":{"roundabout_context":{"method":"measure_roundabout",
                    "value":measure_roundabout(root),"sources":{"map.json":hashes["map.json"]}},
                "motor_operator":{"method":"measure_operator",
                    "value":measure_operator(root),"sources":{"history.json":hashes["history.json"]}},
                "circulation_direction":{"method":"measure_direction",
                    "value":measure_direction(root),
                    "sources":{"map.json":hashes["map.json"],
                               "history.json":hashes["history.json"]}}},
            "diagnostic_fixture":(root/"fixture-provenance.json").is_file(),
            "legal_verdict_claimed":False,
            "limitations":["Signed original ring movement is an observation, not an automated legal verdict.",
                           "CPU fixture pixels do not establish physical Native success."]}
    channels=root/"channels"
    channels.mkdir(exist_ok=False)
    values={"original_roundabout_topology":{"map_sha256":hashes["map.json"],
              "map_name":packet["map_name"]},
            "original_operator_identity":{"history_sha256":hashes["history.json"],
              "actor_id":observed["actor_id"]},
            "original_ring_trajectory":{"history_sha256":hashes["history.json"],
              "signed_arc_rad":observed["signed_arc_rad"],
              "observed_direction":observed["observed_direction"]},
            "original_four_camera_pixels":{"frame_map_sha256":hashes["video_frames.jsonl"],
              "view_count":4}}
    evidence=[]
    for channel in recording["channels"]:
        name=channel["name"]
        if name not in values:
            raise ValueError("unexpected direction channel: "+name)
        rel="channels/"+name+".jsonl"
        (root/rel).write_text("".join(json.dumps({"time_s":row["time_s"],
            "value":values[name]},allow_nan=False)+"\n" for row in trace))
        evidence.append({"name":name,"unit":channel["unit"],"reference":rel})
    context="channels/reviewed_roundabout_map.json"
    (root/context).write_text(json.dumps({"reviewed_roundabout_map":{
        "map_sha256":hashes["map.json"],"jurisdiction":packet["jurisdiction"],
        "legal_judgment":"unresolved"}})+"\n")
    evidence.append({"name":"reviewed_roundabout_map","unit":"source","reference":context})
    result={"case_id":observed["case_id"],"measured_values":observed,
        "target_checks":[{"target":"source-bound circular travel direction",
            "requested":observed["requested_direction"],"measured":observed["observed_direction"],
            "method":"measure_history","tolerance":0,
            "matched":observed["requested_direction"]==observed["observed_direction"],
            "physical_cause_confirmed":False,"cause_evidence":hashes}],
        "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
        "termination_reason":"Saved original source review pending",
        "physical_failure_flags":[],"trace_reference":"trace.jsonl",
        "video_references":[name+".mkv" for name in VIEWS],
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":recording,"recording_evidence":evidence,
        "realized_observables":{},"legal_judgment":None,
        "physical_acceptance_claimed":False}
    (root/"result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    Path(output).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    analyze(args.attempt,args.output)


if __name__ == "__main__":
    main()
