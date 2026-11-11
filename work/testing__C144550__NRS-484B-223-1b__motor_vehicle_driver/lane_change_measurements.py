"""Measure signal ordering and target-lane body gap from original frames.

The driver's actual safety ascertainment has no direct Native observation and
remains unresolved. No legal minimum gap or signal lead time is invented.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("lane_context.json","lane_history.jsonl","video_frames.jsonl")


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
        if not path.is_file():raise ValueError("Missing original source: "+name)
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
        if not contained and first_leave is None:first_leave={"frame":fid,"time_s":time,
                                                             "indicator_at_movement":state}
        ego_span=[min(x*tx+y*ty for x,y in points),max(x*tx+y*ty for x,y in points)]
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
            "first_appropriate_signal":first_signal,"first_body_leaves_lane":first_leave,
            "appropriate_signal_observed_before_movement":signal_preceded,
            "appropriate_signal_active_at_movement":first_leave["indicator_at_movement"]==direction,
            "samples":samples,"driver_ascertained_safety_judgment":"unresolved",
            "target_lane_safety_judgment":"unresolved; no legal numeric gap cutoff",
            "legal_conclusion":"unresolved"}
