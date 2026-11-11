"""Original-frame yield response and non-obligated traffic at a signed junction.

Immediate hazard and cautious proceeding remain judgments, not numeric tests.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("intersection_context.json","entry_history.jsonl","video_frames.jsonl")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _inside(vertices,polygon):
    if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete vehicle body")
    body=MultiPoint([(_number(v[0],"body x"),_number(v[1],"body y")) for v in vertices]).convex_hull
    return body.intersects(polygon)


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"intersection_context.json").read_text())
    for key in ("native_map_id","intersection_id","ego_approach_road_id",
                "other_approach_road_id","native_yield_sign_id","sign_governance_source",
                "entrance_inventory_source","yield_reference_source","highway_status_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced intersection context: "+key)
    if ctx.get("non_through_highway") is not True:
        raise ValueError("Non-through-highway status not sourced")
    if ctx.get("police_control") is not False or ctx.get("traffic_signal_control") is not False:
        raise ValueError("Officer/signal exception unresolved")
    if ctx.get("ego_entrance_device")!="yield":raise ValueError("Ego yield-sign governance missing")
    entrances=ctx.get("entrances")
    if not isinstance(entrances,list) or len(entrances)<2 or any("road_id" not in e or "device" not in e for e in entrances):
        raise ValueError("Incomplete entrance device inventory")
    own=[e for e in entrances if e["road_id"]==ctx["ego_approach_road_id"]]
    other=[e for e in entrances if e["road_id"]==ctx["other_approach_road_id"]]
    if len(own)!=1 or own[0]["device"]!="yield" or len(other)!=1:
        raise ValueError("Entrance obligation identities unresolved")
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid intersection polygon")
    rows,frames=_rows(root/"entry_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete entry history")
    previous=(-1,-math.inf);samples=[];first_entry=None
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("ego_road_id")!=ctx["ego_approach_road_id"] or row.get("yield_sign_id")!=ctx["native_yield_sign_id"]:
            raise ValueError("Ego approach/sign identity mismatch")
        speed=_number(row.get("ego_speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative speed")
        before=row.get("ego_body_before_yield_reference")
        if type(before) is not bool:raise ValueError("Missing yield-reference body position")
        ego_inside=_inside(row.get("ego_body_vertices_xy_m"),polygon)
        other_inside=_inside(row.get("other_body_vertices_xy_m"),polygon)
        if i==0 and ego_inside:raise ValueError("No pre-entry approach")
        if ego_inside and first_entry is None:first_entry={"frame":fid,"time_s":time}
        samples.append({"frame":fid,"time_s":time,"ego_speed_mps":speed,
                        "ego_body_before_yield_reference":before,
                        "ego_body_in_intersection":ego_inside,
                        "other_body_in_intersection":other_inside})
    if first_entry is None:raise ValueError("No observed ego entry")
    prior=[s for s in samples if s["time_s"]<first_entry["time_s"]]
    before_speeds=[s["ego_speed_mps"] for s in prior if s["ego_body_before_yield_reference"]]
    slowed=bool(len(before_speeds)>=2 and min(before_speeds)<before_speeds[0])
    return {"format":"worker-yield-sign-intersection-observations","sources":hashes,
            "first_ego_entry":first_entry,"observed_slowed_or_stopped_before_reference":slowed,
            "other_entrance_device":other[0]["device"],
            "other_not_obligated_by_stop_or_yield":other[0]["device"] not in ("stop","yield"),
            "other_inside_at_ego_entry":next(s["other_body_in_intersection"] for s in samples if s["frame"]==first_entry["frame"]),
            "samples":samples,"immediate_hazard_judgment":"unresolved",
            "caution_and_yield_judgment":"unresolved","legal_conclusion":"unresolved"}
