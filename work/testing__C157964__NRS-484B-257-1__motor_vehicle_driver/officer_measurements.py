"""Original-frame officer-control observations for the statutory exception.

Camera-visible direction and timing are evidence; legal police authority and
whether traffic was actually controlled remain source-review judgments.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


CAMERAS=("overview","approach","reference_corner","driver_reference")
REQUIRED=("officer_context.json","officer_history.jsonl","video_frames.jsonl",
          "officer_review.json")
PREFIX="testing__C157964__NRS-484B-257-1__motor_vehicle_driver__"
ACTIVE={PREFIX+"officer_active_stop_then_go",PREFIX+"officer_active_hold"}
INACTIVE=PREFIX+"officer_present_inactive"
ABSENT=PREFIX+"no_officer_yield_nearest_view"


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
    review=json.loads((root/"officer_review.json").read_text())
    if (review.get("officer_history_sha256")!=hashes["officer_history.jsonl"] or
            review.get("video_frames_sha256")!=hashes["video_frames.jsonl"]):
        raise ValueError("Officer review source hash differs")
    cameras=review.get("camera_sha256")
    if not isinstance(cameras,dict) or set(cameras)!=set(CAMERAS):
        raise ValueError("Four original camera hashes required")
    for camera in CAMERAS:
        path=root/(camera+".mkv")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=cameras[camera]:
            raise ValueError("Original officer camera bytes differ: "+camera)
        hashes[camera+".mkv"]=cameras[camera]
    ctx=json.loads((root/"officer_context.json").read_text())
    case_id=ctx.get("case_id")
    if case_id not in ACTIVE|{INACTIVE,ABSENT}:
        raise ValueError("Unknown exact officer case identity")
    for key in ("native_map_id","intersection_id","direction_video_source",
                "junction_source","ego_route_source"):
        if not ctx.get(key):raise ValueError("Missing sourced officer context: "+key)
    if case_id==ABSENT:
        if any(ctx.get(key) is not None for key in ("officer_actor_id","authority_source","uniform_video_source")):
            raise ValueError("No-officer baseline must lack officer identity and authority")
    else:
        for key in ("officer_actor_id","authority_source","uniform_video_source"):
            if not ctx.get(key):raise ValueError("Missing sourced officer context: "+key)
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid intersection polygon")
    rows,frames=_rows(root/"officer_history.jsonl"),_rows(root/"video_frames.jsonl")
    observations=review.get("frames")
    if (len(rows)<3 or len(rows)!=len(frames) or
            not isinstance(observations,list) or len(observations)!=len(rows)):
        raise ValueError("Incomplete officer/ego camera history")
    previous=(-1,-math.inf);samples=[];first_entry=None
    for i,(row,frame,observed) in enumerate(zip(rows,frames,observations)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if (set(frame.get("camera_frames",{}))!=set(CAMERAS) or
                any(frame["camera_frames"][camera]!=fid for camera in CAMERAS)):
            raise ValueError("Four original camera frame joins required")
        if row.get("officer_actor_id")!=ctx["officer_actor_id"]:
            raise ValueError("Officer actor identity mismatch")
        instruction=observed.get("observed_direction")
        if instruction not in ("stop","go","unclear","none"):
            raise ValueError("Missing original officer direction observation")
        if (observed.get("frame")!=fid or observed.get("video_frame")!=i or
                type(observed.get("officer_visible")) is not bool):
            raise ValueError("Officer camera review direction/frame join failed")
        if "officer_direction_observed" in row or "traffic_control_observed" in row:
            raise ValueError("Capture history must not prelabel camera observations")
        source=observed.get("direction_frame_source")
        if not source:raise ValueError("Missing direction video frame source")
        controlled=observed.get("traffic_control_observed")
        if type(controlled) is not bool:raise ValueError("Missing original control observation")
        if case_id==ABSENT and (controlled or instruction!="none" or observed["officer_visible"]):
            raise ValueError("No-officer baseline contradicts original camera review")
        if case_id==INACTIVE and (controlled or instruction in ("stop","go") or
                                  not observed["officer_visible"]):
            raise ValueError("Inactive officer baseline contradicts original camera review")
        if controlled and (not observed["officer_visible"] or instruction=="unclear"):
            raise ValueError("Claimed active officer control lacks a visible direction")
        if controlled and instruction=="none":
            raise ValueError("Claimed active officer control lacks a direction")
        ego=row.get("ego")
        if not isinstance(ego,dict):raise ValueError("Missing ego source")
        speed=_number(ego.get("speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative ego speed")
        vertices=ego.get("body_vertices_xy_m")
        if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete ego body")
        body=MultiPoint([(_number(p[0],"body x"),_number(p[1],"body y")) for p in vertices]).convex_hull
        inside=body.intersects(polygon)
        if i==0 and inside:raise ValueError("Missing pre-entry approach")
        if inside and first_entry is None:first_entry={"frame":fid,"time_s":time,
                                                       "officer_direction_observed":instruction,
                                                       "traffic_control_observed":controlled,
                                                       "officer_visible":observed["officer_visible"]}
        samples.append({"frame":fid,"time_s":time,"direction":instruction,
                        "traffic_control_observed":controlled,"ego_speed_mps":speed,
                        "ego_body_in_intersection":inside})
    if first_entry is None:raise ValueError("No observed ego entry")
    fixed={key:ctx[key] for key in ("native_map_id","intersection_id",
                                   "intersection_polygon_xy_m","ego_route_source",
                                   "junction_source","direction_video_source")}
    return {"format":"worker-officer-control-exception-observations","case_id":case_id,
            "sources":hashes,
            "fixed_context":fixed,
            "first_ego_entry":first_entry,"officer_control_observed_at_entry":first_entry["traffic_control_observed"],
            "samples":samples,"police_authority_judgment":(
                "not applicable; no officer actor" if case_id==ABSENT else
                "unresolved pending source review"),
            "legal_control_exception_judgment":"unresolved","legal_conclusion":"unresolved"}
