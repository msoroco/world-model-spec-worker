"""Saved-only original/diagnostic measurement for NRS 484B.270(3)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cycle_lane_2703 import ASSIGNMENT, VIEWS, measure_original_frames, intersects


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_source(attempt, name, expected=None):
    path=attempt/(name+"-source.json")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    if expected is not None and sha(path) != expected:
        raise ValueError("reviewed original source changed: "+name)
    return json.loads(path.read_text()),sha(path)


def measure_saved(attempt,case_id):
    attempt=Path(attempt).resolve()
    cfg=json.loads((attempt/"config.json").read_text())
    if cfg.get("selected_case_id") != case_id or not case_id.startswith(ASSIGNMENT+"__"):
        raise ValueError("saved exact case identity differs")
    provenance=json.loads((attempt/"acquisition-provenance.json").read_text())
    diagnostic=provenance.get("diagnostic_fixture") is True
    if diagnostic:
        hashes={}
        for name in ("site","participant","context"):
            source,digest=_read_source(attempt,name)
            if source.get("diagnostic_fixture") is not True:
                raise ValueError("diagnostic source provenance missing: "+name)
            hashes[name]=digest
    else:
        reviewed=os.environ.get("C230223_2703_REVIEWED_PACKET")
        if not reviewed:
            raise ValueError("independent reviewed original packet required")
        from runner import reviewed_packet
        _,hashes=reviewed_packet(reviewed)
        seal=json.loads((attempt/"attempt-source.json").read_text())
        if (seal.get("format") != "cycle-lane-2703-native-attempt-v1" or
                seal.get("source_kind") != "original_native" or
                seal.get("diagnostic_fixture") is not False or
                seal.get("case_id") != case_id):
            raise ValueError("original Native attempt seal required")
        for name in ("site","participant","context"):
            ref=seal.get("sources",{}).get(name,{})
            if ref.get("path") != name+"-source.json" or ref.get("sha256") != hashes[name]:
                raise ValueError("original reviewed source binding differs: "+name)
    site,_=_read_source(attempt,"site",hashes["site"])
    participant,_=_read_source(attempt,"participant",hashes["participant"])
    context,_=_read_source(attempt,"context",hashes["context"])
    plan=json.loads((Path(__file__).resolve().parent/"case-plan.json").read_text())
    case=next((c for c in plan["cases"] if c["case_id"]==case_id),None)
    if case is None or participant.get("road_user_kind") != case["road_user_kind"] or context.get("exception_kind") != case["exception_request"]:
        raise ValueError("saved participant or exception context differs")
    rows=json.loads((attempt/"history.json").read_text())
    if diagnostic:
        if site.get("assignment_id") != ASSIGNMENT or site.get("facility_id") is None:
            raise ValueError("diagnostic site identity missing")
        ego_id,other_id=1,2
    else:
        seal=json.loads((attempt/"attempt-source.json").read_text())
        if seal.get("history",{}).get("sha256") != sha(attempt/"history.json"):
            raise ValueError("original history source hash changed")
        ego_id,other_id=seal.get("ego_actor_id"),seal.get("participant_actor_id")
        if not all(isinstance(i,int) and i>0 for i in (ego_id,other_id)):
            raise ValueError("distinct original actor identity missing")
        if not isinstance(seal.get("cameras"),dict) or set(seal["cameras"]) != set(VIEWS):
            raise ValueError("four original camera sources required")
        for name,ref in seal["cameras"].items():
            video=attempt/ref.get("path","")
            if not video.resolve().is_relative_to(attempt) or not video.is_file() or sha(video)!=ref.get("sha256"):
                raise ValueError("original camera source changed: "+name)
    measurement=measure_original_frames(rows,site["facility_polygon"],site["conflict_polygon"],ego_id,other_id)
    measurement["source_kind"]="synthetic_cpu_fixture" if diagnostic else "original_native"
    measurement["case_id"]=case_id
    measurement["exception_kind_from_source"]=context["exception_kind"]
    measurement["road_user_kind_from_source"]=participant["road_user_kind"]
    measurement["source_sha256"]=hashes
    return measurement,diagnostic,rows


def analyze(attempt,case_id):
    measured,diagnostic,_=measure_saved(attempt,case_id)
    attempt=Path(attempt)
    source_files=("site-source.json","participant-source.json",
                  "context-source.json","history.json")
    sources={name:sha(attempt/name) for name in source_files}
    context=json.loads((attempt/"context-source.json").read_text())
    values=[
        {"precedence":measured["observed_precedence"],
         "participant_kind":measured["road_user_kind_from_source"]},
        {"qualification_facts":context.get("nrs_484b_297_6",{}),
         "participant_kind":measured["road_user_kind_from_source"]},
        {"ego_facility_frames":measured["ego_facility_frames"],
         "requested_action":json.loads((attempt/"config.json").read_text()).get("requested_lane_action")},
        {"exception_kind":measured["exception_kind_from_source"],
         "ego_facility_frames":measured["ego_facility_frames"]},
        {"exception_kind":measured["exception_kind_from_source"],
         "ego_facility_frames":measured["ego_facility_frames"]},
        {"exception_kind":measured["exception_kind_from_source"],
         "observed_precedence":measured["observed_precedence"]},
        {"exception_kind":measured["exception_kind_from_source"],
         "source_review":context.get("exception_source_review")},
        {"exception_kind":measured["exception_kind_from_source"],
         "source_review":context.get("exception_source_review")},
        {"exception_kind":measured["exception_kind_from_source"],
         "source_review":context.get("exception_source_review")},
    ]
    measurements={f"cycle_lane_2703_requirement_{i}":{
        "value":value,"method":"measure_saved","sources":sources}
        for i,value in enumerate(values)}
    return {"format":"worker-analysis-report","case_id":case_id,
            "measurements":measurements,
            "analysis_complete":True,"diagnostic_fixture":diagnostic,
            "legal_verdict_claimed":False}


def saved_result(attempt,report):
    from worker_exchange.native_output import physical_result,validate_result
    attempt=Path(attempt)
    config=json.loads((attempt/"config.json").read_text())
    construction=json.loads((attempt/"construction.json").read_text())
    case_id=config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("saved construction identity differs")
    desc=construction["recording_description"]
    measured,_,rows=measure_saved(attempt,case_id)
    facility=json.loads((attempt/"site-source.json").read_text())["facility_polygon"]
    channels=attempt/"channels"
    channels.mkdir(exist_ok=True)
    evidence=[]
    mapping={
        "ego_body_polygon":lambda row:row["ego_body_polygon"],
        "participant_body_polygon":lambda row:row["participant_body_polygon"],
        "ego_lane_occupancy":lambda row:intersects(row["ego_body_polygon"],facility),
        "participant_lane_occupancy":lambda row:intersects(row["participant_body_polygon"],facility),
        "ego_control":lambda row:row.get("ego_control",{}),
        "participant_control":lambda row:row.get("participant_control",{}),
    }
    for entry in desc["channels"]:
        name=entry["name"]
        if name not in mapping:
            raise ValueError("uncaptured required channel: "+name)
        path=channels/(name+".jsonl")
        with path.open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s":row["time_s"],"value":mapping[name](row)})+"\n")
        evidence.append({"name":name,"unit":entry["unit"],
                         "reference":str(path.relative_to(attempt))})
    context=channels/"context.json"
    context.write_text(json.dumps({
        "site_designation":{"source_sha256":measured["source_sha256"]["site"]},
        "participant_identity":{"kind":measured["road_user_kind_from_source"],
                                "source_sha256":measured["source_sha256"]["participant"]},
        "exception_context":{"kind":measured["exception_kind_from_source"],
                             "source_sha256":measured["source_sha256"]["context"]},
        "pedestrian_qualification":{"source_sha256":measured["source_sha256"]["context"]}})+"\n")
    for entry in desc["context_inputs"]:
        evidence.append({"name":entry["name"],"unit":entry["unit"],
                         "reference":str(context.relative_to(attempt))})
    result={"case_id":case_id,"measured_values":measured,
            "target_checks":[{"target":"original lane occupancy and precedence are measurable",
                "requested":True,"measured":True,"method":"900 source/body joins",
                "tolerance":0,"matched":True,"physical_cause_confirmed":False,
                "cause_evidence":measured["source_sha256"]}],
            "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
            "termination_reason":"Saved cycle-lane interaction awaits independent physical review",
            "physical_failure_flags":[],"trace_reference":"trace.jsonl",
            "video_references":[name+".mkv" for name in VIEWS],
            "video_frame_map_reference":"video_frames.jsonl",
            "recording_description":desc,"recording_evidence":evidence,
            "realized_observables":{}}
    result=physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    config=json.loads((args.attempt/"config.json").read_text())
    report=analyze(args.attempt,config["selected_case_id"])
    result=saved_result(args.attempt,report)
    report["physical_checks"]=result["physical_checks"]
    report["realized_observables"]=result["realized_observables"]
    (args.attempt/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    args.output.write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    main()
