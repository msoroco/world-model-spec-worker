"""Observe active controlling traffic signal at signed-entrance ego entry.

An illuminated light elsewhere at the junction is insufficient. The output
preserves control and timing facts without a legal exception conclusion.
"""

import hashlib
import json
import math
import argparse
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("signal_context.json","signal_history.jsonl","video_frames.jsonl")
CAMERAS=("overview","approach","reference_corner","driver_reference")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"signal_context.json").read_text())
    for key in ("native_map_id","intersection_id","ego_road_id","ego_lane_id",
                "native_signal_id","affected_lane_source","signal_head_video_source",
                "signed_entrance_source","junction_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced signal context: "+key)
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid intersection polygon")
    rows,frames=_rows(root/"signal_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete signal/ego history")
    previous=(-1,-math.inf);samples=[];first_entry=None
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        camera_frames=frame.get("camera_frames")
        if (not isinstance(camera_frames,dict) or set(camera_frames)!=set(CAMERAS) or
                any(camera_frames[name]!=fid for name in CAMERAS)):
            raise ValueError("Four original camera frame joins required")
        if row.get("native_signal_id")!=ctx["native_signal_id"]:
            raise ValueError("Native governing light identity mismatch")
        if row.get("ego_road_id")!=ctx["ego_road_id"] or row.get("ego_lane_id")!=ctx["ego_lane_id"]:
            raise ValueError("Ego outside signal-governed approach")
        state=row.get("signal_state")
        if state not in ("Red","Yellow","Green","Off"):
            raise ValueError("Signal state missing")
        controls=row.get("signal_controls_ego")
        if type(controls) is not bool:raise ValueError("Missing affected-lane control observation")
        speed=_number(row.get("ego_speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative speed")
        vertices=row.get("ego_body_vertices_xy_m")
        if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete ego body")
        body=MultiPoint([(_number(p[0],"body x"),_number(p[1],"body y")) for p in vertices]).convex_hull
        inside=body.intersects(polygon)
        if i==0 and inside:raise ValueError("Missing pre-entry approach")
        if inside and first_entry is None:
            first_entry={"frame":fid,"time_s":time,"signal_state":state,
                         "signal_controls_ego":controls}
        samples.append({"frame":fid,"time_s":time,"signal_state":state,
                        "signal_controls_ego":controls,"ego_speed_mps":speed,
                        "ego_body_in_intersection":inside})
    if first_entry is None:raise ValueError("No observed ego entry")
    active=first_entry["signal_controls_ego"] and first_entry["signal_state"]!="Off"
    return {"format":"worker-controlling-signal-exception-observations","sources":hashes,
            "first_ego_entry":first_entry,"operative_signal_controls_ego_at_entry_observed":active,
            "samples":samples,"official_control_judgment":"unresolved pending source review",
            "legal_exception_judgment":"unresolved","legal_conclusion":"unresolved"}


def measure_operative_signal_at_entry(report):
    return report["operative_signal_controls_ego_at_entry_observed"]


def measure_entry_signal_state(report):
    return report["first_ego_entry"]["signal_state"]


def finalize(attempt, output):
    """Derive primary signal-exception observations from retained originals."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Retain prior C158196 finalization; choose a fresh attempt")
    required = ("config.json", "road.xodr", "trace.jsonl", "capture/evidence.jsonl",
                "signal_context.json", "signal_history.jsonl", "interaction_history.jsonl",
                "control_context.json", "video_frames.jsonl", *(name+".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt/name).is_file() or (attempt/name).stat().st_size == 0:
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt/"config.json").read_text())
    case_id = config.get("selected_case_id")
    prefix = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
    expected = {"signal_controls_ego": True, "signal_visible_not_governing": False,
                "signal_off": False, "yield_without_signal_control": False}
    if not isinstance(case_id, str) or not case_id.startswith(prefix) or case_id[len(prefix):] not in expected:
        raise ValueError("Wrong exact C158196 signal case")
    if config.get("law_id") != "NRS-484B-257-1" or config.get("cell_id") != "C158196":
        raise ValueError("Wrong law or cell identity")
    report = analyze(attempt)
    frames = _rows(attempt/"video_frames.jsonl")
    trace = _rows(attempt/"trace.jsonl")
    interaction = _rows(attempt/"interaction_history.jsonl")
    evidence = _rows(attempt/"capture/evidence.jsonl")
    if (len(frames) != len(trace) or len(frames) != len(interaction) or
            len(frames) != len(evidence)):
        raise ValueError("Original trace, body, evidence and camera histories differ")
    for frame, motion, bodies, event in zip(frames, trace, interaction, evidence):
        fid = frame["carla_frame"]
        if (motion.get("frame") != fid or bodies.get("frame") != fid or
                event.get("original_frame") != fid or
                any(abs(row.get("time_s", -math.inf)-frame["time_s"]) > 1e-6
                    for row in (motion,bodies))):
            raise ValueError("Original trace, body or evidence frame join failed")
        for role in ("ego", "through"):
            body = bodies.get(role, {}).get("body_vertices_m")
            if not isinstance(body, list) or len(body) < 4:
                raise ValueError("Missing complete original interaction body: " + role)
    context = json.loads((attempt/"signal_context.json").read_text())
    control = json.loads((attempt/"control_context.json").read_text())
    if (control.get("intersection_xy_m") != context["intersection_polygon_xy_m"] or
            control.get("native_map_id") != context["native_map_id"]):
        raise ValueError("Original control geometry differs from signal context")
    channels = attempt/"channels"
    channels.mkdir()
    for name, values in {
        "operative_signal_control": [int(sample["signal_controls_ego"] and
                                         sample["signal_state"] != "Off") for sample in report["samples"]],
        "signal_state": [sample["signal_state"] for sample in report["samples"]],
        "ego_crossing_body": [row["ego"] for row in interaction],
    }.items():
        with (channels/(name+".jsonl")).open("x") as stream:
            for frame, value in zip(frames, values):
                stream.write(json.dumps({"original_frame":frame["carla_frame"],
                                         "time_s":frame["time_s"],"value":value},
                                        allow_nan=False)+"\n")
    observed = measure_operative_signal_at_entry(report)
    requested = expected[case_id[len(prefix):]]
    source_hashes = {name:hashlib.sha256((attempt/name).read_bytes()).hexdigest()
                     for name in required}
    result = {"case_id":case_id,
              "measured_values":{"operative_signal_controls_ego_at_entry_observed":observed,
                                 "entry_signal_state":measure_entry_signal_state(report),
                                 "first_ego_entry":report["first_ego_entry"]},
              "target_checks":[{"target":"operative_signal_controls_ego_at_entry_observed",
                                "requested":requested,"measured":observed,
                                "method":"original affected-lane and signal-state join at complete body entry",
                                "tolerance":0,"matched":observed is requested,
                                "physical_cause_confirmed":False,
                                "cause_evidence":["signal_history.jsonl","signal_context.json",
                                                  "interaction_history.jsonl","video_frames.jsonl"]}],
              "setup_confirmed":False,"behavior_attempted":False,
              "maneuver_completed":False,
              "termination_reason":"Saved source analysis; physical source review pending",
              "physical_failure_flags":["official control, head visibility and legal exception remain unresolved"],
              "trace_reference":"trace.jsonl",
              "video_references":[name+".mkv" for name in CAMERAS],
              "video_frame_map_reference":"video_frames.jsonl",
              "recording_description":config["recording_description"],
              "recording_evidence":[{"name":name,"unit":unit,
                                      "reference":"channels/"+name+".jsonl"}
                                     for name,unit in (("operative_signal_control","count"),
                                                       ("signal_state","text"),
                                                       ("ego_crossing_body","structured record"))],
              "source_evidence_hashes":source_hashes,"realized_observables":{}}
    try:
        from worker_exchange.native_output import physical_result, write_result
    except ModuleNotFoundError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"runtime/scenario_pipeline"))
        from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {"format":"worker-c158196-signal-analysis","case_id":case_id,
                "measurements":{
                    "operative_signal_at_entry":{"value":observed,
                        "method":"measure_operative_signal_at_entry",
                        "sources":{name:source_hashes[name] for name in
                                   ("signal_context.json","signal_history.jsonl","video_frames.jsonl")}},
                    "entry_signal_state":{"value":measure_entry_signal_state(report),
                        "method":"measure_entry_signal_state",
                        "sources":{name:source_hashes[name] for name in
                                   ("signal_context.json","signal_history.jsonl","video_frames.jsonl")}}},
                "source_report":report,"physical_checks":result["physical_checks"],
                "realized_observables":result["realized_observables"],
                "legal_conclusion":"unresolved","analysis_complete":True}
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+"\n")
    return analysis


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)
