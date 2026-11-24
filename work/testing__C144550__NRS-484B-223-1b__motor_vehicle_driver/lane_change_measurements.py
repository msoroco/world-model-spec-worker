"""Measure signal ordering and target-lane body gap from original frames.

The driver's actual safety ascertainment has no direct Native observation and
remains unresolved. No legal minimum gap or signal lead time is invented.
"""

import hashlib
import json
import math
import argparse
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("lane_context.json","lane_history.jsonl","video_frames.jsonl")
CASE_PREFIX="testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__"
CASE_PATTERNS={
    "left_signal_before_clear_gap":("left",True,"left"),
    "left_signal_late_clear_gap":("left",False,"left"),
    "left_wrong_signal_clear_gap":("left",False,"right"),
    "left_signal_before_close_gap":("left",True,"left"),
    "right_signal_before_clear_gap":("right",True,"right"),
}


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _shape(vertices):
    if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete body")
    points=[]
    for value in vertices:
        if not isinstance(value,list) or len(value)!=2:raise ValueError("Invalid body vertex")
        points.append((_number(value[0],"body x"),_number(value[1],"body y")))
    shape=MultiPoint(points).convex_hull
    if shape.area<=0:raise ValueError("Degenerate body")
    return shape,points


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing required source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"lane_context.json").read_text())
    for key in ("native_map_id","road_id","source_lane_id","target_lane_id",
                "marked_lane_source","same_direction_lane_count_source","lane_boundary_source",
                "target_traffic_source","signal_display_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced lane context: "+key)
    count=ctx.get("same_direction_marked_lane_count")
    if type(count) is not int or count<2:raise ValueError("Two marked same-direction lanes not sourced")
    direction=ctx.get("change_direction")
    if direction not in ("left","right"):raise ValueError("Lane-change direction missing")
    coords=ctx.get("source_lane_polygon_xy_m")
    if not isinstance(coords,list) or len(coords)<3:raise ValueError("Missing marked source-lane polygon")
    lane=Polygon([(_number(p[0],"lane x"),_number(p[1],"lane y")) for p in coords])
    if not lane.is_valid or lane.area<=0:raise ValueError("Invalid source lane polygon")
    tangent=ctx.get("lane_forward_xy")
    if not isinstance(tangent,list) or len(tangent)!=2:raise ValueError("Missing lane direction")
    tx,ty=(_number(v,"lane forward") for v in tangent)
    norm=math.hypot(tx,ty)
    if norm==0:raise ValueError("Zero lane direction")
    tx,ty=tx/norm,ty/norm
    lane_along=[x*tx+y*ty for x,y in lane.exterior.coords]
    lane_start,lane_end=min(lane_along),max(lane_along)
    lanes=ctx.get("same_direction_lanes")
    if not isinstance(lanes,list) or len(lanes)!=count:
        raise ValueError("Same-direction lane inventory/count mismatch")
    ids=set()
    for item in lanes:
        if not isinstance(item,dict) or item.get("road_id")!=ctx["road_id"]:
            raise ValueError("Same-direction lane road mismatch")
        ident=item.get("lane_id")
        if type(ident) is not int or ident==0 or ident in ids:
            raise ValueError("Duplicate or invalid same-direction lane identity")
        ids.add(ident)
        vec=item.get("forward_xy")
        if not isinstance(vec,list) or len(vec)!=2:
            raise ValueError("Same-direction lane heading missing")
        vx,vy=(_number(v,"lane heading") for v in vec)
        magnitude=math.hypot(vx,vy)
        if magnitude==0 or (vx*tx+vy*ty)/magnitude<=0:
            raise ValueError("Opposing lane in same-direction inventory")
        if not item.get("marking_source"):
            raise ValueError("Lane marking source missing")
    if ctx["source_lane_id"] not in ids or ctx["target_lane_id"] not in ids:
        raise ValueError("Source or target lane missing from same-direction inventory")
    if (ctx["source_lane_id"]>0)!=(ctx["target_lane_id"]>0):
        raise ValueError("Source and target lane IDs have opposing Native signs")
    rows,frames=_rows(root/"lane_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete lane-change history")
    previous=(-1,-math.inf);first_signal=None;first_leave=None;samples=[]
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("road_id")!=ctx["road_id"]:
            raise ValueError("Ego road identity mismatch")
        state=row.get("indicator")
        if state not in ("off","left","right"):raise ValueError("Missing measured indicator state")
        body,points=_shape(row.get("ego_body_vertices_xy_m"))
        if i==0 and not lane.covers(body):raise ValueError("No fully contained original starting frame")
        if state==direction and first_signal is None:first_signal={"frame":fid,"time_s":time}
        contained=lane.covers(body)
        ego_span=[min(x*tx+y*ty for x,y in points),max(x*tx+y*ty for x,y in points)]
        if not contained and first_leave is None:
            if ego_span[0]<lane_start or ego_span[1]>lane_end:
                raise ValueError("Source-lane longitudinal extent exhausted before lateral departure")
            first_leave={"frame":fid,"time_s":time,"indicator_at_movement":state}
        gaps=[]
        others=row.get("target_lane_bodies")
        if not isinstance(others,list):raise ValueError("Missing target-lane participant inventory")
        for other in others:
            if other.get("road_id")!=ctx["road_id"] or other.get("lane_id")!=ctx["target_lane_id"]:
                raise ValueError("Target-lane participant mismatch")
            _,other_points=_shape(other.get("body_vertices_xy_m"))
            span=[min(x*tx+y*ty for x,y in other_points),max(x*tx+y*ty for x,y in other_points)]
            gap=max(span[0]-ego_span[1],ego_span[0]-span[1])
            gaps.append(gap)
        samples.append({"frame":fid,"time_s":time,"indicator":state,
                        "ego_body_fully_in_source_lane":contained,
                        "nearest_target_body_longitudinal_gap_m":min(gaps) if gaps else None})
    if first_leave is None:raise ValueError("No observed movement out of source lane")
    signal_preceded=bool(first_signal and first_signal["time_s"]<first_leave["time_s"])
    return {"format":"worker-lane-change-prerequisite-observations","sources":hashes,
            "same_direction_lane_ids":sorted(ids),
            "first_appropriate_signal":first_signal,"first_body_leaves_lane":first_leave,
            "appropriate_signal_observed_before_movement":signal_preceded,
            "appropriate_signal_active_at_movement":first_leave["indicator_at_movement"]==direction,
            "samples":samples,"driver_ascertained_safety_judgment":"unresolved",
            "target_lane_safety_judgment":"unresolved; no legal numeric gap cutoff",
            "legal_conclusion":"unresolved"}


def measure_exact_case(root:Path,case_id:str,expected_frames:int=900)->dict:
    """Bind a planned exact case to observed original rows, without legal inference.

    A mismatch is evidence about the realized attempt, not a reason to rewrite
    the observation or silently classify the driver's safety judgment.
    """
    suffix=case_id[len(CASE_PREFIX):] if isinstance(case_id,str) and case_id.startswith(CASE_PREFIX) else ""
    if suffix not in CASE_PATTERNS:raise ValueError("Unknown exact lane-change case")
    if type(expected_frames) is not int or expected_frames<3:
        raise ValueError("Valid expected frame count required")
    root=Path(root)
    observations=analyze(root)
    if len(observations["samples"])!=expected_frames:
        raise ValueError("Incomplete original lane-change frame count")
    ctx=json.loads((root/"lane_context.json").read_text())
    direction,preceded,signal_at_movement=CASE_PATTERNS[suffix]
    if ctx["change_direction"]!=direction:
        raise ValueError("Exact case and original lane direction differ")
    movement=observations["first_body_leaves_lane"]
    sample=next(row for row in observations["samples"] if row["frame"]==movement["frame"])
    observed={
        "appropriate_signal_before_movement":observations["appropriate_signal_observed_before_movement"],
        "indicator_at_movement":movement["indicator_at_movement"],
        "nearest_target_body_longitudinal_gap_at_movement_m":sample["nearest_target_body_longitudinal_gap_m"],
    }
    return {
        "format":"worker-lane-change-exact-saved-measurements",
        "case_id":case_id,"source_frame_count":expected_frames,
        "sources":observations["sources"],
        "planned_signal_pattern":{"change_direction":direction,
                                  "appropriate_signal_before_movement":preceded,
                                  "indicator_at_movement":signal_at_movement},
        "observed":observed,
        "observed_signal_pattern_matches_plan":(
            observed["appropriate_signal_before_movement"]==preceded and
            observed["indicator_at_movement"]==signal_at_movement),
        "first_appropriate_signal":observations["first_appropriate_signal"],
        "first_body_leaves_lane":movement,
        "same_direction_lane_ids":observations["same_direction_lane_ids"],
        "driver_ascertained_safety_judgment":"unresolved",
        "target_lane_safety_judgment":"unresolved; no legal numeric gap cutoff",
        "legal_conclusion":"unresolved",
    }


def write_saved_measurements(root:Path,case_id:str,output:Path,expected_frames:int=900)->dict:
    """Persist the source-bound report for a later saved-processing finalizer."""
    report=measure_exact_case(root,case_id,expected_frames)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+".tmp")
    temporary.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    temporary.replace(output)
    return report


def persist_original_sources(root:Path,context:dict,rows:list,expected_frames:int=900)->dict:
    """Save retained Native lane rows and their original frame map once.

    The caller supplies map and marking context observed at the Native site.
    Raw camera files are acquired separately; this method never synthesizes
    images or substitutes requested indicator commands for observed display.
    """
    if type(expected_frames) is not int or expected_frames<3 or not isinstance(rows,list) or len(rows)!=expected_frames:
        raise ValueError("Incomplete original lane-change frame count")
    if not isinstance(context,dict):raise ValueError("Original lane context required")
    root=Path(root)
    if any((root/name).exists() for name in REQUIRED):
        raise ValueError("Original lane-change sources already exist")
    frames=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or type(row.get("frame")) is not int:
            raise ValueError("Original Native frame identity required")
        frames.append({"video_frame":index,"carla_frame":row["frame"],
                       "time_s":row.get("time_s")})
    root.mkdir(parents=True,exist_ok=True)
    payloads={
        "lane_context.json":json.dumps(context,sort_keys=True,indent=2)+"\n",
        "lane_history.jsonl":"".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),
        "video_frames.jsonl":"".join(json.dumps(frame,sort_keys=True)+"\n" for frame in frames),
    }
    try:
        for name,payload in payloads.items():
            (root/name).write_text(payload)
        return analyze(root)
    except Exception:
        for name in REQUIRED:
            (root/name).unlink(missing_ok=True)
        raise


CAMERAS=("overview.mkv","approach.mkv","reference_corner.mkv","driver_reference.mkv")


def validate_physical_binding(root:Path,config:dict)->None:
    """Prevent the generic lane-transition checker from targeting another lane."""
    root=Path(root)
    context=json.loads((root/"lane_context.json").read_text())
    descriptor=config.get("physical_completion")
    if not isinstance(descriptor,dict) or any((
        descriptor.get("body_key")!="ego_body_vertices_xy_m",
        descriptor.get("lane_key")!="ego_lane_id",
        descriptor.get("destination_lane")!=context["target_lane_id"],
        descriptor.get("context_sources")!=["lane_context.json"],
    )):
        raise ValueError("Physical lane-transition descriptor differs from original target lane")
    rows=_rows(root/"lane_history.jsonl")
    if any(type(row.get("ego_lane_id")) is not int for row in rows):
        raise ValueError("Original ego lane readback missing")
    if rows[0]["ego_lane_id"]!=context["source_lane_id"]:
        raise ValueError("Original ego start lane differs from sourced source lane")


def finalize(attempt:Path,output:Path)->dict:
    """Build the saved result and channels from retained original acquisition.

    The caller runs this only in the saved-processing stage. Runtime media and
    physical checks still assess the produced result independently.
    """
    from worker_exchange.native_output import physical_result,write_result
    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Retain prior finalization; use a fresh attempt")
    for name in ("config.json","trace.jsonl",*REQUIRED,*CAMERAS):
        if not (attempt/name).is_file():raise ValueError("Missing required source: "+name)
    config=json.loads((attempt/"config.json").read_text())
    case_id=config.get("selected_case_id")
    description=config.get("recording_description") or config.get("case",{}).get("recording_description")
    if not isinstance(description,dict) or not description.get("channels"):
        raise ValueError("Selected recording description required")
    report=measure_exact_case(attempt,case_id)
    validate_physical_binding(attempt,config)
    observations=analyze(attempt)
    channel_dir=attempt/"channels";channel_dir.mkdir()
    channels={
        "indicator_state":("categorical",lambda sample:sample["indicator"]),
        "body_fully_in_source_lane":("boolean",lambda sample:sample["ego_body_fully_in_source_lane"]),
        "nearest_target_body_longitudinal_gap_m":("m",lambda sample:sample["nearest_target_body_longitudinal_gap_m"]),
        "source_lane_body_departure":("boolean",lambda sample:not sample["ego_body_fully_in_source_lane"]),
        "indicator_before_departure":("boolean",lambda sample:sample["indicator"]==json.loads((attempt/"lane_context.json").read_text())["change_direction"]),
        "target_lane_gap":("m",lambda sample:sample["nearest_target_body_longitudinal_gap_m"]),
    }
    evidence=[]
    for name,(unit,extract) in channels.items():
        path=channel_dir/(name+".jsonl")
        with path.open("x") as stream:
            for sample in observations["samples"]:
                stream.write(json.dumps({"original_frame":sample["frame"],
                                         "time_s":sample["time_s"],
                                         "value":extract(sample)},allow_nan=False)+"\n")
        evidence.append({"name":name,"unit":unit,"reference":"channels/"+path.name})
    lane_inventory={"marked_same_direction_lane_inventory":json.loads((attempt/"lane_context.json").read_text())["same_direction_lanes"]}
    inventory_path=channel_dir/"marked_same_direction_lane_inventory.json"
    inventory_path.write_text(json.dumps(lane_inventory,sort_keys=True)+"\n")
    evidence.append({"name":"marked_same_direction_lane_inventory","unit":"structured record",
                     "reference":"channels/"+inventory_path.name})
    check={"target":"planned appropriate indicator pattern at first body departure",
           "requested":True,"measured":report["observed_signal_pattern_matches_plan"],
           "method":"original indicator state and complete body departure from marked source-lane polygon",
           "tolerance":0,"matched":report["observed_signal_pattern_matches_plan"],
           "physical_cause_confirmed":False,
           "cause_evidence":["lane_context.json","lane_history.jsonl","video_frames.jsonl"]}
    result={"case_id":case_id,
            "measured_values":report["observed"],"target_checks":[check],
            "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
            "termination_reason":"Original lane-change sources assessed; safety and legal judgments unresolved",
            "physical_failure_flags":["actual marking and displayed lamp require source-camera review",
                                      "driver safety ascertainment is not directly observable"],
            "trace_reference":"trace.jsonl","video_references":list(CAMERAS),
            "video_frame_map_reference":"video_frames.jsonl",
            "recording_description":description,"recording_evidence":evidence,
            "source_evidence_hashes":report["sources"],"realized_observables":{}}
    result=physical_result(attempt,result)
    analysis={"format":"worker-lane-change-analysis","case_id":case_id,
              "measurements":{"signal_and_gap_at_movement":{
                  "method":"measure_exact_case","value":report["observed"],
                  "sources":report["sources"]}},
              "source_report":report,"source_hashes":report["sources"],
              "physical_checks":result["physical_checks"],
              "driver_ascertained_safety_judgment":"unresolved",
              "legal_verdict_asserted":False}
    write_result(attempt,result)
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+"\n")
    return analysis


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    finalize(Path(args.attempt),Path(args.output))


if __name__=="__main__":main()
