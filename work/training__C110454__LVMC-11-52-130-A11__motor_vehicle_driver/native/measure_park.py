"""Saved-source measurement of parked body distance to an intersection."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FIFTEEN_FEET_M = 4.572


def measure(source: Path, expected_sha256: str) -> dict:
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Original Native source hash differs")
    packet = json.loads(source.read_text())
    if packet.get("source_kind") != "native_frame_schema" or packet.get("intersection_boundary_source") != "native_map_readback":
        raise ValueError("Original Native map boundary source is absent")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 480:
        raise ValueError("Need complete 480-frame Native source")
    boundary = packet.get("intersection_entry_boundary_x_m")
    if not isinstance(boundary, (int,float)) or not math.isfinite(boundary):
        raise ValueError("Missing surveyed intersection boundary")
    resting = []
    first_frame=frames[0].get("native_frame")
    first_time=frames[0].get("time_s")
    if type(first_frame) is not int or not isinstance(first_time,(int,float)) or not math.isfinite(first_time):
        raise ValueError("Original frame/time join differs")
    for i, row in enumerate(frames):
        if row.get("video_frame") != i or row.get("native_frame") != first_frame+i or abs(row.get("time_s",-1) - first_time-i*.05) > 1e-6:
            raise ValueError("Original frame/time join differs")
        body = row.get("body_xy_m")
        if not isinstance(body,list) or len(body)!=4 or any(not isinstance(p,list) or len(p)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in body):
            raise ValueError("Original body footprint absent")
        speed = row.get("speed_m_s")
        if not isinstance(speed,(int,float)) or not math.isfinite(speed) or speed<0:
            raise ValueError("Observed speed absent")
        if speed<=.05:
            resting.append((i, min(p[0] for p in body)-boundary))
    if len(resting)<40 or any(b[0]!=a[0]+1 for a,b in zip(resting,resting[1:])):
        raise ValueError("Continuous 2-second parked interval absent")
    distances=[d for _,d in resting]
    if min(distances)<0:
        raise ValueError("Parked body extends into intersection")
    relation=("boundary_unresolved" if abs(min(distances)-FIFTEEN_FEET_M)<.05 else
              "within_15_ft" if min(distances)<FIFTEEN_FEET_M else "outside_15_ft")
    return {"source_sha256":expected_sha256,"rest_frames":len(resting),
            "nearest_parked_body_distance_m":min(distances),
            "sampled_relation":relation,
            "threshold_m":FIFTEEN_FEET_M,"lawful_conflict_or_direction_exception_proven":False,
            "native_physical_observation_claimed":False,"legal_verdict":None}


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("source",type=Path)
    parser.add_argument("--sha256",required=True)
    args=parser.parse_args()
    print(json.dumps(measure(args.source,args.sha256),sort_keys=True))
