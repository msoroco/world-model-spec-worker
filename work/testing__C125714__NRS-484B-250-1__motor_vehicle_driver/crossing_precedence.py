"""Original-frame other-before-ego entry at one median-opening crossing."""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon

REQUIRED=("junction_context.json","crossing_history.jsonl","video_frames.jsonl")

def _finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)

def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def _body(actor):
    values=actor.get("body_vertices_xy_m")
    if not isinstance(values,list) or len(values)<4:raise ValueError("Missing complete body")
    points=[]
    for point in values:
        if not isinstance(point,list) or len(point)!=2:raise ValueError("Invalid body vertex")
        points.append((_finite(point[0],"body x"),_finite(point[1],"body y")))
    body=MultiPoint(points).convex_hull
    if body.area<=0:raise ValueError("Degenerate body")
    return body

def analyze(root:Path, *, allow_exceptions=False)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"junction_context.json").read_text())
    for key in ("native_map_id","intersection_id","ego_highway_id","other_highway_id",
                "ego_road_id","other_road_id","crossing_geometry_source","all_entrances_source",
                "official_device_inventory_source","median_spacing_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced crossing context: "+key)
    if ctx["ego_highway_id"]==ctx["other_highway_id"] or ctx.get("same_statutory_crossing") is not True:
        raise ValueError("Different-highway same-crossing activation not sourced")
    if ctx.get("official_device_controls_crossing") is not False:
        raise ValueError("Official-device exclusion unresolved")
    exception=ctx.get("opposite_approach_with_left_turn")
    if type(exception) is not bool:
        raise ValueError("Opposite-direction left-turn exclusion unresolved")
    if exception and not allow_exceptions:
        raise ValueError("Opposite-direction left-turn exclusion unresolved")
    crossing=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not crossing.is_valid or crossing.area<=0:raise ValueError("Invalid crossing polygon")
    rows,frames=_rows(root/"crossing_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete entry history")
    first={"ego":None,"other":None};samples=[];prev=(-1,-math.inf)
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_finite(row.get("time_s"),"time")
        if type(fid) is not int or fid<=prev[0] or time<=prev[1]:raise ValueError("Nonmonotone original history")
        prev=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original video frame join failed")
        sample={"frame":fid,"time_s":time}
        for role in ("ego","other"):
            actor=row.get(role)
            if not isinstance(actor,dict) or actor.get("intersection_id")!=ctx["intersection_id"] or actor.get("road_id")!=ctx[role+"_road_id"]:
                raise ValueError("Participant crossing identity mismatch")
            inside=_body(actor).intersects(crossing)
            if i==0 and inside:raise ValueError("Missing pre-entry history")
            if inside and first[role] is None:first[role]={"frame":fid,"time_s":time}
            sample[role+"_inside"]=inside
        if row.get("ego_vertices_m") != row["ego"]["body_vertices_xy_m"]:
            raise ValueError("Pinned physical ego body differs from measured original body")
        samples.append(sample)
    if not all(first.values()):raise ValueError("Both original body entries required")
    other_before=first["other"]["time_s"]<first["ego"]["time_s"]
    other_at_ego=next(s["other_inside"] for s in samples if s["frame"]==first["ego"]["frame"])
    return {"format":"worker-median-crossing-other-precedence","sources":hashes,"first_body_entry":first,
            "other_enters_before_ego":other_before,"other_body_inside_at_ego_entry":other_at_ego,
            "opposite_approach_with_left_turn":exception,
            "subsection_1_applicable_on_declared_exception":not exception,
            "entry_time_difference_s":first["ego"]["time_s"]-first["other"]["time_s"],
            "samples":samples,"yield_judgment":"unresolved; body entry alone does not establish yielding",
            "legal_conclusion":"unresolved"}
