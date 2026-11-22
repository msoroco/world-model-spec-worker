"""Saved-only standing/passage/sight measurements from original Native rows.

The result measures physical geometry and original motion. Pixel visibility,
district classification, practicability, unavoidable stopping and legal
adequacy remain explicit separate questions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from standing_geometry import STATUTORY_SIGHT_DISTANCE_M,overlaps,rectangle,segment_crosses_rect
from native_construction import ASSIGNMENT,validate_scene

SOURCES=("construction.json","scene.json","authored-road.xodr","road.xodr","trace.jsonl",
         "video_frames.jsonl","standing-body-history.jsonl","passing-body-history.jsonl",
         "occluder-body-history.jsonl","mechanical-attempt-history.jsonl")
VIDEOS=("overview.mkv","approach.mkv","reference_corner.mkv","driver_reference.mkv")


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    result=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(result)<3:raise ValueError("missing sufficient original rows: "+str(path))
    return result


def body_rect(row):
    points=row.get("body_vertices_xy_m")
    if not isinstance(points,list) or len(points)!=4 or any(not isinstance(p,list) or len(p)!=2 for p in points):
        raise ValueError("missing original four-corner actor body")
    return rectangle([min(p[0] for p in points),min(p[1] for p in points),
                      max(p[0] for p in points),max(p[1] for p in points)],"original actor body")


def _center(rect):return ((rect[0]+rect[2])/2,(rect[1]+rect[3])/2)


def _join(mapping,standing,passing,occluders,mechanism):
    if not len(mapping)==len(standing)==len(passing)==len(occluders)==len(mechanism):
        raise ValueError("original frame stream lengths differ")
    previous=(-1,-math.inf)
    for index,group in enumerate(zip(mapping,standing,passing,occluders,mechanism)):
        anchor=group[0];frame=anchor.get("carla_frame");time=anchor.get("time_s")
        if type(frame) is not int or type(time) not in (int,float) or not math.isfinite(time):
            raise ValueError("invalid original frame identity")
        if frame<=previous[0] or time<=previous[1] or anchor.get("video_frame")!=index:
            raise ValueError("nonmonotonic original frame or video index")
        for row in group[1:]:
            if row.get("frame")!=frame or abs(row.get("time_s",math.inf)-time)>1e-4:
                raise ValueError("original frame/time join failed")
        if mechanism[index].get("standing_actor_id")!=standing[index].get("actor_id"):
            raise ValueError("mechanism actor identity differs")
        previous=(frame,time)


def measure_original(scene,mapping,standing,passing,occluders,mechanism):
    """Measure every saved frame; do not infer legal standards from dimensions."""
    _join(mapping,standing,passing,occluders,mechanism)
    road=rectangle(scene["paved_road_xy_m"],"paved road")
    standing_bodies=[body_rect(row) for row in standing]
    passing_bodies=[body_rect(row) for row in passing]
    positions=[_center(rect) for rect in passing_bodies]
    standing_positions=[_center(rect) for rect in standing_bodies]
    max_drift=max(math.dist(standing_positions[0],p) for p in standing_positions)
    # Even if collision physics prevents penetration, project the observed
    # passing body's dimensions onto its authored lane at the standing x.
    first_passing=passing_bodies[0]
    passing_half_length=(first_passing[2]-first_passing[0])/2
    passing_half_width=(first_passing[3]-first_passing[1])/2
    lane_y=positions[0][1]
    stop_x=standing_positions[0][0]
    projected_body=(stop_x-passing_half_length,lane_y-passing_half_width,
                    stop_x+passing_half_length,lane_y+passing_half_width)
    corridor_interference=any(overlaps(projected_body,standing_body) for standing_body in standing_bodies)
    collisions=[mapping[i]["carla_frame"] for i,(a,b) in enumerate(zip(standing_bodies,passing_bodies)) if overlaps(a,b)]
    outside=[mapping[i]["carla_frame"] for i,b in enumerate(passing_bodies)
             if b[0]<road[0] or b[2]>road[2] or b[1]<road[1] or b[3]>road[3]]
    width=[road[3]-b[3] if scene["standing_side"]=="negative_y" else b[1]-road[1]
           for b in standing_bodies]
    if any(not isinstance(row.get("actors"),list) or
           len(row["actors"])!=len(scene["sight_occluders_xy_m"]) for row in occluders):
        raise ValueError("original occluder actor count differs from construction")
    probes={}
    middle=len(mapping)//2
    target=_center(standing_bodies[middle])
    prop_bodies=[body_rect(row) for row in occluders[middle]["actors"]]
    for side in (-1,1):
        for distance in scene["sight_probe_distances_m"]:
            eye=(side*distance,scene["sight_eye_y_m"])
            hits=[i for i,body in enumerate(prop_bodies) if segment_crosses_rect(eye,target,body)]
            probes[f"{'negative_x' if side<0 else 'positive_x'}:{distance:.3f}m"]={
                "eye_xy_m":eye,"target_xy_m":target,"actual_prop_hit_indices":hits,
                "clear_xy_geometry":not hits,"optical_visibility":"unverified_requires_original_pixels"}
    route_completed=positions[0][0]>40 and positions[-1][0]<-40
    stopped=max_drift<=.5
    mechanical_attempt=all(row.get("physics_disabled_by_worker") is True and
                           row.get("brake_requested")==1. and
                           row.get("hand_brake_requested") is True for row in mechanism)
    return {"frame_count":len(mapping),"first_frame":mapping[0]["carla_frame"],
            "last_frame":mapping[-1]["carla_frame"],
            "statutory_sight_distance_m":STATUTORY_SIGHT_DISTANCE_M,
            "unobstructed_opposite_width_m_by_frame":width,
            "minimum_unobstructed_opposite_width_m":min(width),
            "standing_max_drift_m":max_drift,"standing_stationary_engineering_check":stopped,
            "passing_start_end_x_m":[positions[0][0],positions[-1][0]],
            "passing_route_completed_engineering_check":route_completed,
            "passing_body_collision_frames":collisions,"passing_body_outside_paved_frames":outside,
            "opposite_route_corridor_interference":corridor_interference,
            "physical_passage_observed":route_completed and stopped and not collisions and not outside,
            "actual_prop_bodies_xy_m":prop_bodies,"sight_probes":probes,
            "mechanical_disable_and_brake_attempt_observed":mechanical_attempt,
            "unavoidable_stopping":"unverified","temporary_duration_legal_relevance":"unverified",
            "highway_and_district_status":"unverified","off_pavement_practicability":"unverified",
            "legal_adequacy_judgment":"unresolved","legal_verdict_claimed":False}


def _decode_video(path,expected):
    """Fully decode and count frames, retaining the video hash in the receipt."""
    probe=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-count_frames",
        "-show_entries","stream=nb_read_frames,width,height,r_frame_rate","-of","json",str(path)],
        capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout).get("streams",[])
    if len(streams)!=1 or int(streams[0].get("nb_read_frames",-1))!=expected:
        raise ValueError("media frame count differs: "+path.name)
    if streams[0].get("r_frame_rate")!="20/1":raise ValueError("media frame rate differs")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(path),
                    "-f","null","-"],capture_output=True,check=True)
    return {"sha256":sha(path),"frames_fully_decoded":expected,
            "width":streams[0]["width"],"height":streams[0]["height"],"fps":20}


def finalize(root):
    root=Path(root).resolve()
    seal=root/"capture-seal.json"
    if not seal.is_file():raise ValueError("unsealed Native capture")
    sealed=json.loads(seal.read_text())
    if sealed.get("diagnostic_fixture") or sealed.get("restoration",{}).get("restored") is not True:
        raise ValueError("non-Native or unrestored capture")
    source_hashes={}
    for name in (*SOURCES,*VIDEOS,"acquisition.json"):
        path=root/name
        if not path.is_file():raise ValueError("missing original source: "+name)
        source_hashes[name]=sha(path)
    acquisition=json.loads((root/"acquisition.json").read_text())
    for name in (*SOURCES[1:],*VIDEOS):
        if acquisition.get(name,{}).get("sha256")!=source_hashes[name]:
            raise ValueError("acquisition source binding differs: "+name)
    scene=json.loads((root/"scene.json").read_text())
    validate_scene(scene,root/"authored-road.xodr")
    if not scene["case_id"].startswith(ASSIGNMENT+"__"):
        raise ValueError("case assignment differs")
    paths=[root/name for name in ("video_frames.jsonl","standing-body-history.jsonl",
                                  "passing-body-history.jsonl","occluder-body-history.jsonl",
                                  "mechanical-attempt-history.jsonl")]
    mapping,standing,passing,occluders,mechanism=[rows(path) for path in paths]
    measured=measure_original(scene,mapping,standing,passing,occluders,mechanism)
    if sealed.get("frames")!=measured["frame_count"]:raise ValueError("seal frame count differs")
    media={name:_decode_video(root/name,measured["frame_count"]) for name in VIDEOS}
    result={"format":"c135705-source-bound-standing-measurement","case_id":scene["case_id"],
            "provenance_kind":"native","source_sha256":source_hashes,
            "capture_seal_sha256":sha(seal),"media_full_decode":media,
            "measured":measured,"physical_acceptance_claimed":False}
    output=root/"standing-measurement.json"
    if output.exists():raise ValueError("saved measurement already exists")
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument("attempt")
    args=parser.parse_args();result=finalize(args.attempt)
    print(json.dumps({"case_id":result["case_id"],"frames":result["measured"]["frame_count"],
                      "output":"standing-measurement.json"}))


if __name__=="__main__":main()
