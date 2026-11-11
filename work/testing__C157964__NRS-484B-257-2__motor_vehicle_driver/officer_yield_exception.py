"""Original-frame officer-control observations for the statutory exception.

Camera-visible direction and timing are evidence; legal police authority and
whether traffic was actually controlled remain source-review judgments.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("officer_context.json","officer_history.jsonl","video_frames.jsonl")


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
    ctx=json.loads((root/"officer_context.json").read_text())
    for key in ("native_map_id","intersection_id","officer_actor_id",
                "authority_source","uniform_video_source","direction_video_source",
                "junction_source","ego_route_source","sign_inventory_source",
                "other_entrance_source","highway_status_source"):
        if not ctx.get(key):raise ValueError("Missing sourced officer context: "+key)
    if ctx.get("non_through_highway") is not True or ctx.get("ego_entrance_device") not in ("stop","yield"):
        raise ValueError("Signed non-through entrance not sourced")
    if ctx.get("other_entrance_device") in ("stop","yield",None):
        raise ValueError("Non-obligated other entrance not sourced")
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid intersection polygon")
    rows,frames=_rows(root/"officer_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete officer/ego history")
    previous=(-1,-math.inf);samples=[];first_entry=None
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("officer_actor_id")!=ctx["officer_actor_id"]:
            raise ValueError("Officer actor identity mismatch")
        instruction=row.get("officer_direction_observed")
        if instruction not in ("stop","go","unclear"):
            raise ValueError("Missing original officer direction observation")
        source=row.get("direction_frame_source")
        if not source:raise ValueError("Missing direction video frame source")
        controlled=row.get("traffic_control_observed")
        if type(controlled) is not bool:raise ValueError("Missing original control observation")
        ego=row.get("ego")
        if not isinstance(ego,dict):raise ValueError("Missing ego source")
        speed=_number(ego.get("speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative ego speed")
        vertices=ego.get("body_vertices_xy_m")
        if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete ego body")
        body=MultiPoint([(_number(p[0],"body x"),_number(p[1],"body y")) for p in vertices]).convex_hull
        inside=body.intersects(polygon)
        other_vertices=row.get("other_body_vertices_xy_m")
        if not isinstance(other_vertices,list) or len(other_vertices)<4:raise ValueError("Missing other vehicle body")
        other=MultiPoint([(_number(p[0],"other x"),_number(p[1],"other y")) for p in other_vertices]).convex_hull
        other_inside=other.intersects(polygon)
        if i==0 and inside:raise ValueError("Missing pre-entry approach")
        if inside and first_entry is None:first_entry={"frame":fid,"time_s":time,
                                                       "officer_direction_observed":instruction,
                                                       "traffic_control_observed":controlled}
        samples.append({"frame":fid,"time_s":time,"direction":instruction,
                        "traffic_control_observed":controlled,"ego_speed_mps":speed,
                        "ego_body_in_intersection":inside,"other_body_in_intersection":other_inside})
    if first_entry is None:raise ValueError("No observed ego entry")
    return {"format":"worker-officer-control-exception-observations","sources":hashes,
            "first_ego_entry":first_entry,"officer_control_observed_at_entry":first_entry["traffic_control_observed"],
            "other_inside_at_ego_entry":next(s["other_body_in_intersection"] for s in samples if s["frame"]==first_entry["frame"]),
            "subsection_2_applicability":"officer_control_exception_candidate" if first_entry["traffic_control_observed"] else "signed_entrance_candidate",
            "samples":samples,"police_authority_judgment":"unresolved pending source review",
            "legal_control_exception_judgment":"unresolved","legal_conclusion":"unresolved"}
