"""Original-frame body position relative to sourced two-way approach centerline.

Distance and right-half containment are physical observations. The legal phrase
"nearest the centerline" has no numeric cutoff here.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import LineString, MultiPoint, Point, Polygon


REQUIRED=("road_context.json","approach_history.jsonl","video_frames.jsonl")


def _finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _points(values,label,minimum):
    if not isinstance(values,list) or len(values)<minimum:
        raise ValueError("Missing "+label)
    points=[]
    for value in values:
        if not isinstance(value,list) or len(value)!=2:
            raise ValueError("Invalid "+label)
        points.append((_finite(value[0],label+" x"),_finite(value[1],label+" y")))
    return points


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"road_context.json").read_text())
    for key in ("native_map_id","intersection_id","approach_road_id","approach_lane_id",
                "outgoing_road_id","opposing_lane_source","centerline_source",
                "right_half_source","junction_source","left_turn_route_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced road context: "+key)
    if ctx.get("both_highways_two_directional") is not True or ctx.get("intended_turn")!="left":
        raise ValueError("Two-directional left-turn activation not sourced")
    centerline=LineString(_points(ctx.get("centerline_xy_m"),"centerline",2))
    right_half=Polygon(_points(ctx.get("right_half_polygon_xy_m"),"right half",3))
    if centerline.length<=0 or not right_half.is_valid or right_half.area<=0:
        raise ValueError("Invalid road reference geometry")
    rows,frames=_rows(root/"approach_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<2 or len(rows)!=len(frames):raise ValueError("Incomplete approach/frame history")
    previous=(-1,-math.inf);samples=[]
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_finite(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("road_id")!=ctx["approach_road_id"] or row.get("lane_id")!=ctx["approach_lane_id"]:
            raise ValueError("Ego outside sourced approach lane")
        if row.get("body_in_intersection") is not False:
            raise ValueError("Approach sample must precede intersection entry")
        vertices=_points(row.get("ego_body_vertices_xy_m"),"ego body",4)
        body=MultiPoint(vertices).convex_hull
        if body.area<=0:raise ValueError("Degenerate vehicle body")
        distances=[centerline.distance(Point(point)) for point in vertices]
        samples.append({"frame":fid,"time_s":time,"body_fully_in_right_half":right_half.covers(body),
                        "minimum_body_vertex_distance_to_centerline_m":min(distances),
                        "maximum_body_vertex_distance_to_centerline_m":max(distances),
                        "body_centroid_distance_to_centerline_m":centerline.distance(body.centroid)})
    return {"format":"worker-left-approach-centerline-observations","sources":hashes,
            "native_road_context":ctx,"approach_samples":samples,
            "all_sampled_bodies_in_right_half":all(s["body_fully_in_right_half"] for s in samples),
            "nearest_centerline_judgment":"unresolved; no statutory numeric lateral cutoff",
            "legal_conclusion":"unresolved"}
