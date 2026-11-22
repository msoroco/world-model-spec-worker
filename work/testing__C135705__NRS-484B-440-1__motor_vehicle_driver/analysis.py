"""Saved-only C135705 finalizer for Native attempts and diagnostic fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_construction import validate_scene
from saved_measurement import measure_original as _measure_original,rows,finalize

REQUIRED=("trace.jsonl","video_frames.jsonl","standing-body-history.jsonl","passing-body-history.jsonl",
          "occluder-body-history.jsonl","mechanical-attempt-history.jsonl")
MEASUREMENT=("standing-body-history.jsonl","passing-body-history.jsonl",
             "occluder-body-history.jsonl","mechanical-attempt-history.jsonl",
             "video_frames.jsonl","trace.jsonl","approach.mkv","reference_corner.mkv")


def measure_original(scene,mapping,standing,passing,props,mechanical):
    return _measure_original(scene,mapping,standing,passing,props,mechanical)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root,acquisition,name,kind):
    path=root/name
    if not path.is_file():raise ValueError("Missing required source: "+name)
    item=acquisition.get(name,{})
    if item.get("kind")!=kind or item.get("sha256")!=sha(path):
        raise ValueError("Missing or stale provenance-bound source: "+name)
    return path


def build_report(attempt):
    root=Path(attempt).resolve()
    provenance=json.loads((root/"acquisition-provenance.json").read_text())
    native=provenance.get("provenance_kind")=="native" and provenance.get("diagnostic_fixture") is False
    diagnostic=provenance.get("provenance_kind")=="synthetic_fixture" and provenance.get("diagnostic_fixture") is True
    if not native and not diagnostic:raise ValueError("contradictory acquisition provenance")
    kind="original_native" if native else "diagnostic_fixture"
    acquisition=json.loads((root/"acquisition.json").read_text())
    paths={name:source(root,acquisition,name,kind) for name in REQUIRED}
    scene=json.loads((root/"scene.json").read_text())
    validate_scene(scene,root/("authored-road.xodr" if native else "road.xodr"))
    mapping,standing,passing,props,mechanical=[rows(paths[name]) for name in (
        "video_frames.jsonl","standing-body-history.jsonl","passing-body-history.jsonl",
        "occluder-body-history.jsonl","mechanical-attempt-history.jsonl")]
    trace=rows(paths["trace.jsonl"])
    if len(trace)!=len(mapping) or any(a.get("carla_frame")!=b.get("frame") for a,b in zip(mapping,trace)):
        raise ValueError("original trace/frame map join failed")
    if native:
        # Fully decode all original cameras and require the restored-world seal.
        sealed=finalize(root)
        observed=sealed["measured"]
    else:
        observed=measure_original(scene,mapping,standing,passing,props,mechanical)
    return {"format":"worker-analysis-report","analysis_complete":True,
        "measurements":{"standing_passage_two_sided_sight_measurement":{
            "value":observed,"method":"measure_original",
            "sources":{name:sha(root/name) for name in MEASUREMENT}}},
        "provenance_kind":"native" if native else "synthetic_fixture",
        "limitations":["Two-sided XY ray geometry does not establish original-pixel clear view.",
            "Highway/district status, off-pavement practicability, free-passage legal adequacy and subsection (2) exception remain for source review."],
        "legal_verdict_claimed":False}


def saved_result(attempt,report):
    from worker_exchange.native_output import physical_result,validate_result
    root=Path(attempt).resolve();config=json.loads((root/"config.json").read_text())
    construction=json.loads((root/"construction.json").read_text())
    scene=json.loads((root/"scene.json").read_text())
    if (config.get("law_id"),config.get("cell_id"),config.get("actor"))!=("NRS-484B-440-1","C135705","motor_vehicle_driver"):
        raise ValueError("saved finalizer assignment identity differs")
    if config.get("selected_case_id")!=scene["case_id"]:
        raise ValueError("exact case differs from source scene")
    description=construction["recording_description"]
    if description!=config["case"]["recording_description"]:
        raise ValueError("recording description differs from exact config")
    provenance=json.loads((root/"acquisition-provenance.json").read_text())
    acquisition=json.loads((root/"acquisition.json").read_text())
    kind="original_native" if provenance["provenance_kind"]=="native" else "diagnostic_fixture"
    standing=rows(source(root,acquisition,"standing-body-history.jsonl",kind))
    passing=rows(source(root,acquisition,"passing-body-history.jsonl",kind))
    props=rows(source(root,acquisition,"occluder-body-history.jsonl",kind))
    mechanism=rows(source(root,acquisition,"mechanical-attempt-history.jsonl",kind))
    values={"standing_body_xy_m":[(r["time_s"],r["body_vertices_xy_m"]) for r in standing],
            "other_vehicle_body_xy_m":[(r["time_s"],r["body_vertices_xy_m"]) for r in passing],
            "two_sided_200ft_sight":[(r["time_s"],[a["body_vertices_xy_m"] for a in r["actors"]]) for r in props],
            "mechanical_failure_attempt":[(r["time_s"],{
                "physics_disabled_by_worker":r["physics_disabled_by_worker"],
                "brake_requested":r["brake_requested"],
                "duration_since_first_sample_s":r.get("duration_since_first_sample_s")}) for r in mechanism]}
    channel_dir=root/"channels";channel_dir.mkdir(exist_ok=True)
    evidence=[]
    for item in description["channels"]:
        name=item["name"]
        if name not in values:raise ValueError("unsupported declared channel: "+name)
        path=channel_dir/(name+".jsonl")
        with path.open("x") as stream:
            for time,value in values[name]:stream.write(json.dumps({"time_s":time,"value":value},allow_nan=False)+"\n")
        evidence.append({"name":name,"unit":item["unit"],"reference":str(path.relative_to(root))})
    map_path=root/("authored-road.xodr" if kind=="original_native" else "road.xodr")
    contexts={"authored_road":{"sha256":sha(map_path),
                               "paved_road_xy_m":scene["paved_road_xy_m"]},
              "district_review":scene["administrative_context"]}
    context_path=channel_dir/"context.json";context_path.write_text(json.dumps(contexts,allow_nan=False)+"\n")
    for item in description["context_inputs"]:
        evidence.append({"name":item["name"],"unit":item["unit"],
                         "reference":str(context_path.relative_to(root))})
    observed=report["measurements"]["standing_passage_two_sided_sight_measurement"]["value"]
    suffix=scene["case_id"].rsplit("__",1)[1]
    actual=[observed["physical_passage_observed"],
            observed["sight_probes"]["negative_x:60.960m"]["clear_xy_geometry"],
            observed["sight_probes"]["positive_x:60.960m"]["clear_xy_geometry"]]
    expected={"passage_clear_view":[True,True,True],"passage_blocked":[False,True,True],
              "view_occluded_both":[True,False,False]}[suffix]
    targets=[{"target":name,"requested":request,"measured":value,
              "method":"source-bound original full-body and actual-prop geometry",
              "tolerance":0,"matched":value==request,"physical_cause_confirmed":False,
              "cause_evidence":report["measurements"]["standing_passage_two_sided_sight_measurement"]["sources"]}
             for name,value,request in zip(("free physical passage","negative 200-foot XY view",
                                            "positive 200-foot XY view"),actual,expected)]
    result={"case_id":scene["case_id"],"measured_values":observed,"target_checks":targets,
        "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
        "termination_reason":"Saved source review and physical completion pending",
        "physical_failure_flags":[],"trace_reference":"trace.jsonl",
        "video_references":["overview.mkv","approach.mkv","reference_corner.mkv","driver_reference.mkv"],
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":description,"recording_evidence":evidence,"realized_observables":{}}
    result=physical_result(root,result)
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True);args=parser.parse_args()
    report=build_report(args.attempt);result=saved_result(args.attempt,report)
    report["physical_checks"]=result["physical_checks"]
    report["realized_observables"]=result["realized_observables"]
    with (Path(args.attempt)/"result.json").open("x") as stream:
        stream.write(json.dumps(result,indent=2,allow_nan=False)+"\n")
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":main()
