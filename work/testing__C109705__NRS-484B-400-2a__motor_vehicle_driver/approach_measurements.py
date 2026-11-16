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
    if len(rows)<2 or len(rows)>len(frames):raise ValueError("Incomplete approach/frame history")
    if len(rows)<len(frames) and ctx.get("first_entry_frame")!=frames[len(rows)].get("carla_frame"):
        raise ValueError("First intersection entry does not follow complete approach prefix")
    previous=(-1,-math.inf);samples=[]
    for i,(row,frame) in enumerate(zip(rows,frames[:len(rows)])):
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


def compare_near_far(near_root:Path, far_root:Path)->dict:
    """Compare independently saved approaches with fixed sourced road geometry.

    Frame numbers and physical trajectories may differ between attempts. The
    geometric distinction is observational and supplies no legal cutoff.
    """
    near,far=analyze(near_root),analyze(far_root)
    fixed=("native_map_id","intersection_id","approach_road_id",
           "approach_lane_id","outgoing_road_id","opposing_lane_source",
           "centerline_source","right_half_source","junction_source",
           "left_turn_route_source","both_highways_two_directional",
           "intended_turn","centerline_kind","centerline_xy_m",
           "right_half_polygon_xy_m")
    a,b=near["native_road_context"],far["native_road_context"]
    if any(a.get(key)!=b.get(key) for key in fixed):
        raise ValueError("Fixed approach road context differs")
    if not near["all_sampled_bodies_in_right_half"] or not far["all_sampled_bodies_in_right_half"]:
        raise ValueError("Compared body leaves sourced right half")
    near_distances=[s["body_centroid_distance_to_centerline_m"] for s in near["approach_samples"]]
    far_distances=[s["body_centroid_distance_to_centerline_m"] for s in far["approach_samples"]]
    near_mean=sum(near_distances)/len(near_distances)
    far_mean=sum(far_distances)/len(far_distances)
    if not near_mean<far_mean:
        raise ValueError("Near/far measured ordering missing")
    return {"format":"worker-left-approach-near-far-comparison",
            "fixed_context_keys":list(fixed),
            "near_source_hashes":near["sources"],"far_source_hashes":far["sources"],
            "near_mean_body_centroid_distance_m":near_mean,
            "far_mean_body_centroid_distance_m":far_mean,
            "legal_nearest_judgment":"unresolved"}


def finalize(attempt:Path, output:Path)->dict:
    """Rebuild C109705(2a) measurements from saved original sources only."""
    from worker_exchange.native_output import physical_result, write_result

    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Use fresh saved analysis output and retain original evidence")
    required=("config.json","road_context.json","road_geometry.json",
              "approach_history.jsonl","body_history.jsonl","video_frames.jsonl",
              "trace.jsonl","capture/evidence.jsonl",
              "overview.mkv","approach.mkv","reference_corner.mkv","driver_reference.mkv")
    for name in required:
        if not (attempt/name).is_file():
            raise ValueError("Missing required source: "+name)
    config=json.loads((attempt/"config.json").read_text())
    case="testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__source_verified_near_centerline"
    if (config.get("selected_case_id"),config.get("law_id"),config.get("cell_id"),
            config.get("actor"))!=(case,"NRS-484B-400-2a","C109705","motor_vehicle_driver"):
        raise ValueError("Exact saved C109705(2a) case identity differs")
    if not isinstance(config.get("recording_description"),dict):
        raise ValueError("Saved recording description missing")
    observations=analyze(attempt)
    if not observations["all_sampled_bodies_in_right_half"]:
        raise ValueError("Observed approach body leaves sourced right half")
    context=observations["native_road_context"]
    if context.get("centerline_kind")!="marked":
        raise ValueError("First selected case requires sourced marked centerline")
    mapping=_rows(attempt/"video_frames.jsonl")
    body_rows=_rows(attempt/"body_history.jsonl")
    if len(body_rows)!=len(mapping) or not body_rows:
        raise ValueError("Body history does not cover every original frame")
    for i,(body,frame) in enumerate(zip(body_rows,mapping)):
        if (body.get("frame")!=frame.get("carla_frame") or
                body.get("time_s")!=frame.get("time_s") or
                frame.get("video_frame")!=i):
            raise ValueError("Full body history original-frame join failed")
        vertices=body.get("body_vertices_m")
        if (not isinstance(vertices,list) or len(vertices)<4 or
                any(not isinstance(v,list) or len(v)<3 or
                    any(type(n) not in (int,float) or not math.isfinite(n) for n in v[:3])
                    for v in vertices)):
            raise ValueError("Incomplete original full-body vertices")
    sources={name:hashlib.sha256((attempt/name).read_bytes()).hexdigest() for name in required}
    samples=observations["approach_samples"]
    measured={"approach_body_fully_in_right_half":True,
              "sampled_approach_frames":len(samples),
              "body_centroid_centerline_distance_m":[row["body_centroid_distance_to_centerline_m"] for row in samples],
              "body_minimum_vertex_centerline_distance_m":[row["minimum_body_vertex_distance_to_centerline_m"] for row in samples],
              "first_entry_frame":context.get("first_entry_frame"),
              "nearest_centerline_judgment":"unresolved; no statutory numeric cutoff"}
    channels=attempt/"channels";channels.mkdir()
    (channels/"approach_context.json").write_text(json.dumps({
        "case_id":case,"measurements":measured,"source_evidence_hashes":sources,
        "legal_conclusion":"unresolved"},indent=2,allow_nan=False)+"\n")
    (channels/"approach_lateral.jsonl").write_text("".join(json.dumps({
        "time_s":row["time_s"],"value":{"frame":row["frame"],
        "body_fully_in_right_half":row["body_fully_in_right_half"],
        "body_centroid_distance_to_centerline_m":row["body_centroid_distance_to_centerline_m"]}},
        allow_nan=False)+"\n" for row in samples))
    result={"case_id":case,"measured_values":measured,
        "target_checks":[{"target":"complete_body_right_half_approach",
          "requested":True,"measured":True,"method":"original full-body polygon and sourced right-half intersection",
          "tolerance":0,"matched":True,"physical_cause_confirmed":False,
          "cause_evidence":["road_context.json","approach_history.jsonl","video_frames.jsonl"]}],
        "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
        "termination_reason":"Saved original-source analysis; physical and legal review pending",
        "physical_failure_flags":["actual Native motion and camera visibility not independently accepted"],
        "trace_reference":"trace.jsonl",
        "video_references":[name+".mkv" for name in ("overview","approach","reference_corner","driver_reference")],
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":config["recording_description"],
        "recording_evidence":[{"name":"approach_context","unit":"structured record",
                               "reference":"channels/approach_context.json"},
                              {"name":"approach_lateral","unit":"meters and boolean",
                               "reference":"channels/approach_lateral.jsonl"}],
        "source_evidence_hashes":sources,"capture_evidence_sha256":sources["capture/evidence.jsonl"],
        "realized_observables":{}}
    result=physical_result(attempt,result)
    write_result(attempt,result)
    report={"format":"worker-c109705-approach-saved-analysis","case_id":case,
            "measurements":measured,"sources":sources,
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return report


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps({"case_id":finalize(args.attempt,args.output)["case_id"],
                      "physical_acceptance_claimed":False}))
