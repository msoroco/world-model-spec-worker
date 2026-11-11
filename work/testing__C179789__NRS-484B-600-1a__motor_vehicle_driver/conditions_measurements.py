"""Measure speed with frame-specific traffic, surface, width and weather.

The stopping-distance calculation is a declared engineering diagnostic. It is
not a statutory definition of 'reasonable or proper'.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED=("road_context.json","condition_history.jsonl","video_frames.jsonl")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _speed(velocity):
    if not isinstance(velocity,list) or len(velocity)!=3:
        raise ValueError("Missing Native 3D velocity")
    return math.sqrt(sum(_number(v,"velocity component")**2 for v in velocity))


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"road_context.json").read_text())
    for key in ("native_map_id","ego_actor_id","road_id","lane_id",
                "road_surface_source","lane_width_source","traffic_source",
                "weather_source","sight_source","curvature_source",
                "braking_model_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced speed context: "+key)
    reaction=_number(ctx.get("diagnostic_reaction_time_s"),"diagnostic reaction time")
    decel=_number(ctx.get("diagnostic_braking_deceleration_mps2"),"diagnostic deceleration")
    if reaction<0 or decel<=0:raise ValueError("Invalid declared engineering braking model")
    rows,frames=_rows(root/"condition_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<2 or len(rows)!=len(frames):raise ValueError("Incomplete original condition history")
    previous=(-1,-math.inf);samples=[]
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        if row.get("ego_actor_id")!=ctx["ego_actor_id"] or row.get("road_id")!=ctx["road_id"] or row.get("lane_id")!=ctx["lane_id"]:
            raise ValueError("Ego source road/actor mismatch")
        if row.get("ego_velocity_source")!="actor.get_velocity":
            raise ValueError("Ego Native velocity source missing")
        speed=_speed(row.get("ego_velocity_mps"))
        lane_width=_number(row.get("lane_width_m"),"lane width")
        sight=_number(row.get("sight_distance_m"),"sight distance")
        curvature=_number(row.get("curvature_per_m"),"curvature")
        precip=_number(row.get("precipitation_percent"),"precipitation")
        if lane_width<=0 or sight<0 or curvature<0 or not 0<=precip<=100:
            raise ValueError("Invalid frame-specific highway condition")
        if row.get("surface") not in ("dry","wet","ice_or_snow"):
            raise ValueError("Surface condition not source-resolved")
        traffic=row.get("surrounding_traffic")
        if not isinstance(traffic,list):raise ValueError("Missing surrounding-traffic inventory")
        actors=[]
        for other in traffic:
            if not other.get("actor_id") or other.get("velocity_source")!="actor.get_velocity":
                raise ValueError("Surrounding-traffic Native source missing")
            gap=_number(other.get("longitudinal_body_gap_m"),"traffic body gap")
            actors.append({"actor_id":other["actor_id"],"speed_mps":_speed(other.get("velocity_mps")),
                           "longitudinal_body_gap_m":gap})
        stop_distance=speed*reaction+speed*speed/(2*decel)
        samples.append({"frame":fid,"time_s":time,"ego_speed_mps":speed,
                        "lane_width_m":lane_width,"surface":row["surface"],
                        "precipitation_percent":precip,"sight_distance_m":sight,
                        "curvature_per_m":curvature,"surrounding_traffic":actors,
                        "diagnostic_stopping_distance_m":stop_distance,
                        "diagnostic_stop_distance_exceeds_sight":stop_distance>sight})
    return {"format":"worker-basic-speed-conditions-observations","sources":hashes,
            "engineering_model":{"reaction_time_s":reaction,"braking_deceleration_mps2":decel,
                                 "source":ctx["braking_model_source"],"legal_threshold":False},
            "samples":samples,"reasonable_or_proper_judgment":"unresolved",
            "legal_conclusion":"unresolved"}
