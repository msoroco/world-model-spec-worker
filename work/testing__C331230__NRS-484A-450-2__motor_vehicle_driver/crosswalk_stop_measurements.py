"""Observe a complete halt before the near-side crosswalk, then junction entry.

NRS 484A.450(2) selects the crosswalk first, even when a marked stop line also
exists. This reports physical ordering without a legal compliance verdict.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("approach_context.json","stop_history.jsonl","video_frames.jsonl")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _points(values,label,minimum):
    if not isinstance(values,list) or len(values)<minimum:raise ValueError("Missing "+label)
    points=[]
    for value in values:
        if not isinstance(value,list) or len(value)!=2:raise ValueError("Invalid "+label)
        points.append((_number(value[0],label+" x"),_number(value[1],label+" y")))
    return points


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"approach_context.json").read_text())
    for key in ("native_map_id","intersection_id","approach_road_id","approach_lane_id",
                "native_stop_sign_id","sign_governance_source","crosswalk_source",
                "crosswalk_nearside_source","junction_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced approach context: "+key)
    if ctx.get("near_side_crosswalk_exists") is not True:
        raise ValueError("Selected near-side crosswalk absent")
    if ctx.get("crosswalk_origin") not in ("marked","sidewalk_connection"):
        raise ValueError("Crosswalk marking or sidewalk source missing")
    crosswalk=Polygon(_points(ctx.get("crosswalk_polygon_xy_m"),"crosswalk polygon",3))
    junction=Polygon(_points(ctx.get("intersection_polygon_xy_m"),"intersection polygon",3))
    if not crosswalk.is_valid or crosswalk.area<=0 or not junction.is_valid or junction.area<=0:
        raise ValueError("Invalid crosswalk or junction geometry")
    forward=ctx.get("approach_forward_xy")
    if not isinstance(forward,list) or len(forward)!=2:raise ValueError("Missing approach direction")
    fx,fy=(_number(v,"approach direction") for v in forward)
    norm=math.hypot(fx,fy)
    if norm==0:raise ValueError("Zero approach direction")
    fx,fy=fx/norm,fy/norm
    nearest_crosswalk=min(x*fx+y*fy for x,y in _points(ctx["crosswalk_polygon_xy_m"],"crosswalk",3))
    rows,frames=_rows(root/"stop_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<4 or len(rows)!=len(frames):raise ValueError("Incomplete stop/crosswalk history")
    previous=(-1,-math.inf);samples=[];first_cross=None;first_junction=None;first_stop=None
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("road_id")!=ctx["approach_road_id"] or row.get("lane_id")!=ctx["approach_lane_id"] or row.get("stop_sign_id")!=ctx["native_stop_sign_id"]:
            raise ValueError("Ego approach/sign identity mismatch")
        speed=_number(row.get("ego_speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative ego speed")
        points=_points(row.get("ego_body_vertices_xy_m"),"complete ego body",4)
        body=MultiPoint(points).convex_hull
        before=max(x*fx+y*fy for x,y in points)<nearest_crosswalk
        in_cross=body.intersects(crosswalk)
        in_junction=body.intersects(junction)
        if i==0 and (in_cross or in_junction):raise ValueError("Missing pre-crosswalk approach")
        if speed==0 and before and first_stop is None:first_stop={"frame":fid,"time_s":time}
        if in_cross and first_cross is None:first_cross={"frame":fid,"time_s":time}
        if in_junction and first_junction is None:first_junction={"frame":fid,"time_s":time}
        samples.append({"frame":fid,"time_s":time,"ego_speed_mps":speed,
                        "body_wholly_before_nearside_crosswalk":before,
                        "body_in_crosswalk":in_cross,"body_in_intersection":in_junction})
    if first_cross is None or first_junction is None:
        raise ValueError("Crosswalk and junction entry must both be observed")
    ordered=bool(first_stop and first_stop["time_s"]<first_cross["time_s"]<first_junction["time_s"])
    return {"format":"worker-nearside-crosswalk-stop-observations","sources":hashes,
            "selected_reference":"near_side_crosswalk",
            "stop_line_present_but_lower_priority":ctx.get("stop_line_exists") is True,
            "first_full_halt_before_crosswalk":first_stop,
            "first_crosswalk_entry":first_cross,"first_intersection_entry":first_junction,
            "full_halt_before_crosswalk_and_junction_observed":ordered,
            "samples":samples,"legal_conclusion":"unresolved"}
