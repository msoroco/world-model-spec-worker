"""Original-frame complete-body route through a divided-highway opening."""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("divider_context.json","movement_history.jsonl","video_frames.jsonl")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _polygon(values,label):
    if not isinstance(values,list) or len(values)<3:raise ValueError("Missing "+label)
    poly=Polygon([(_number(v[0],label+" x"),_number(v[1],label+" y")) for v in values])
    if not poly.is_valid or poly.area<=0:raise ValueError("Invalid "+label)
    return poly


def _body(values):
    if not isinstance(values,list) or len(values)<4:raise ValueError("Missing complete body")
    body=MultiPoint([(_number(v[0],"body x"),_number(v[1],"body y")) for v in values]).convex_hull
    if body.area<=0:raise ValueError("Degenerate body")
    return body


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"divider_context.json").read_text())
    for key in ("native_map_id","divided_highway_source","roadway_boundaries_source",
                "opening_geometry_source","barrier_actors_source","other_vehicle_source",
                "public_authority_source","uturn_route_source"):
        if not ctx.get(key):raise ValueError("Missing sourced divider context: "+key)
    right=_polygon(ctx.get("right_hand_roadway_xy_m"),"right-hand roadway")
    destination=_polygon(ctx.get("destination_roadway_xy_m"),"destination roadway")
    divider=_polygon(ctx.get("dividing_space_xy_m"),"dividing space")
    opening=_polygon(ctx.get("opening_xy_m"),"opening")
    if not divider.covers(opening):raise ValueError("Opening not within dividing space")
    blocked=divider.difference(opening)
    rows,frames=_rows(root/"movement_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<4 or len(rows)!=len(frames):raise ValueError("Incomplete movement history")
    previous=(-1,-math.inf);samples=[];gears=[]
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        ego=_body(row.get("ego_body_vertices_xy_m"))
        other=_body(row.get("other_body_vertices_xy_m"))
        heading=row.get("ego_forward_xy")
        if not isinstance(heading,list) or len(heading)!=2:raise ValueError("Missing ego heading")
        hx,hy=(_number(v,"ego heading") for v in heading)
        norm=math.hypot(hx,hy)
        if norm==0:raise ValueError("Zero ego heading")
        gear=row.get("ego_gear")
        if gear not in ("forward","reverse"):raise ValueError("Missing original ego gear")
        gears.append(gear)
        samples.append({"frame":fid,"ego_gear":gear,"time_s":time,"ego_in_right_roadway":ego.intersects(right),
                        "ego_in_destination_roadway":ego.intersects(destination),
                        "ego_in_opening":ego.intersects(opening),
                        "ego_over_divider_outside_opening":ego.intersects(blocked),
                        "other_body_distance_m":ego.distance(other),
                        "ego_forward_xy":[hx/norm,hy/norm]})
    first,last=samples[0],samples[-1]
    before,after=first["ego_forward_xy"],last["ego_forward_xy"]
    turn=math.degrees(math.atan2(before[0]*after[1]-before[1]*after[0],
                                 before[0]*after[0]+before[1]*after[1]))
    changes=sum(a!=b for a,b in zip(gears,gears[1:]))
    return {"format":"worker-divided-road-uturn-observations","sources":hashes,
            "starts_on_right_hand_roadway":first["ego_in_right_roadway"],
            "ends_on_destination_roadway":last["ego_in_destination_roadway"],
            "opening_traversed_observed":any(s["ego_in_opening"] for s in samples),
            "any_body_overlap_outside_opening":any(s["ego_over_divider_outside_opening"] for s in samples),
            "observed_turn_angle_degrees":turn,"gear_changes":changes,
            "multiple_movement_observed":changes>=2,"samples":samples,
            "public_authority_establishment_judgment":"unresolved",
            "legal_conclusion":"unresolved"}
