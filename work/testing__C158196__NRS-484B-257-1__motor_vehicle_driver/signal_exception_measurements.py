"""Observe active controlling traffic signal at signed-entrance ego entry.

An illuminated light elsewhere at the junction is insufficient. The output
preserves control and timing facts without a legal exception conclusion.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("signal_context.json","signal_history.jsonl","video_frames.jsonl")


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
