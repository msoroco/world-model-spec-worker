"""Source-bound entry-time and right-side geometry at one median crossing.

The elapsed time is reported without inventing a legal 'approximately' cutoff.
Off-state and official-device/subsection-4 questions remain separate review.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED=("crossing_history.jsonl","video_frames.jsonl","junction_context.json")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _body(actor):
    values=actor.get("body_vertices_xy_m")
    if not isinstance(values,list) or len(values)<4:
        raise ValueError("Missing complete body")
    points=[]
    for point in values:
        if not isinstance(point,list) or len(point)!=2:raise ValueError("Invalid body vertex")
        points.append((_number(point[0],"body x"),_number(point[1],"body y")))
    body=MultiPoint(points).convex_hull
    if body.area<=0:raise ValueError("Degenerate body")
    return body


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"junction_context.json").read_text())
    for key in ("native_map_id","intersection_id","ego_highway_id","other_highway_id",
                "ego_road_id","other_road_id","crossing_geometry_source",
                "all_entrances_source","signal_governance_source","signal_head_video_source",
                "median_spacing_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced crossing context: "+key)
    if ctx["ego_highway_id"]==ctx["other_highway_id"]:
        raise ValueError("Approaches are not from different highways")
    if ctx.get("same_statutory_crossing") is not True:
        raise ValueError("One median-opening roadway crossing not sourced")
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid crossing polygon")
    rows,frames=_rows(root/"crossing_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete entry history")
    first={"ego":None,"other":None};start={};samples=[];previous=(-1,-math.inf)
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original video frame join failed")
        if row.get("governing_signal_state")!="Off":
            raise ValueError("Governing Native signal not observed Off")
        sample={"frame":fid,"time_s":time}
        for role in ("ego","other"):
            actor=row.get(role)
            if not isinstance(actor,dict) or actor.get("intersection_id")!=ctx["intersection_id"] or actor.get("road_id")!=ctx[role+"_road_id"]:
                raise ValueError("Participant crossing identity mismatch")
            # The selected measurement is entry of the complete vehicle body.
            # Boundary contact alone can precede that event by several frames.
            body=_body(actor);inside=polygon.covers(body)
            if i==0:
                if inside:raise ValueError("Missing pre-entry history")
                start[role]=(body.centroid.x,body.centroid.y)
            if inside and first[role] is None:first[role]={"frame":fid,"time_s":time}
            sample[role]={"body_in_crossing":inside}
        samples.append(sample)
    if not all(first.values()):raise ValueError("Both original body entries required")
    forward=ctx.get("ego_approach_forward_xy")
    if not isinstance(forward,list) or len(forward)!=2:raise ValueError("Ego approach bearing missing")
    fx,fy=(_number(v,"approach direction") for v in forward)
    norm=math.hypot(fx,fy)
    if norm==0:raise ValueError("Zero approach direction")
    dx=start["other"][0]-start["ego"][0]
    dy=start["other"][1]-start["ego"][1]
    right_cross=(fx*dy-fy*dx)/norm
    return {"format":"worker-median-crossing-entry-timing","sources":hashes,
            "first_body_entry":first,"absolute_entry_time_difference_s":abs(first["ego"]["time_s"]-first["other"]["time_s"]),
            "other_spatially_right_of_ego_approach":right_cross<0,
            "other_right_signed_cross_m":right_cross,"samples":samples,
            "approximately_same_time_judgment":"unresolved; no legal numeric window",
            "opposite_direction_left_turn_exception_judgment":"unresolved",
            "official_device_subsection_4_judgment":"unresolved",
            "yield_judgment":"unresolved","legal_conclusion":"unresolved"}
