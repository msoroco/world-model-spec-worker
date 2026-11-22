"""CPU geometry for standing width, actual passage and two-sided 200 ft sight lines.

This measures physical candidate scenes only. District, practicability, disability
and legal adequacy remain separately sourced judgment questions.
"""
from __future__ import annotations

import math

FEET_TO_METRES = 0.3048
STATUTORY_SIGHT_DISTANCE_M = 200 * FEET_TO_METRES


def rectangle(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value) or
            value[0] >= value[2] or value[1] >= value[3]):
        raise ValueError("invalid finite rectangle: " + name)
    return tuple(float(v) for v in value)


def overlaps(a, b):
    a, b = rectangle(a, "first"), rectangle(b, "second")
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def segment_crosses_rect(start, end, rect):
    """Liang-Barsky closed-segment test; touching occluder counts as obscured."""
    x0,y0 = start; x1,y1 = end
    rect = rectangle(rect, "occluder")
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (*start,*end)):
        raise ValueError("nonfinite sight endpoint")
    dx,dy = x1-x0,y1-y0
    lo,hi = 0.0,1.0
    for p,q in ((-dx,x0-rect[0]),(dx,rect[2]-x0),(-dy,y0-rect[1]),(dy,rect[3]-y0)):
        if p == 0:
            if q < 0:return False
        else:
            t=q/p
            if p < 0:lo=max(lo,t)
            else:hi=min(hi,t)
            if lo > hi:return False
    return True


def measure(scene):
    road = rectangle(scene["paved_road_xy_m"], "paved road")
    standing = rectangle(scene["standing_body_xy_m"], "standing body")
    if not (road[0] <= standing[0] and standing[2] <= road[2]):
        raise ValueError("standing body outside authored road length")
    direction = scene["standing_side"]
    if direction not in ("negative_y", "positive_y"):
        raise ValueError("unknown standing side")
    opposite_width = road[3]-standing[3] if direction=="negative_y" else standing[1]-road[1]
    if opposite_width < 0:
        opposite_width = 0.0
    route = scene["other_vehicle_centers_xy_m"]
    if not isinstance(route,list) or len(route)<3:
        raise ValueError("passing vehicle route needs original trajectory samples")
    half_length,half_width = scene["other_vehicle_half_length_m"],scene["other_vehicle_half_width_m"]
    if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (half_length,half_width)):
        raise ValueError("invalid passing vehicle dimensions")
    bodies = [[x-half_length,y-half_width,x+half_length,y+half_width] for x,y in route]
    collisions=[i for i,body in enumerate(bodies) if overlaps(body,standing)]
    outside=[i for i,body in enumerate(bodies)
             if body[0]<road[0] or body[2]>road[2] or body[1]<road[1] or body[3]>road[3]]
    eye_y = scene["sight_eye_y_m"]
    target = [(standing[0]+standing[2])/2,(standing[1]+standing[3])/2]
    occluders=[rectangle(value,"sight occluder") for value in scene.get("sight_occluders_xy_m",[])]
    probes={}
    for side in (-1,1):
        for distance in scene["sight_probe_distances_m"]:
            if type(distance) not in (int,float) or not math.isfinite(distance) or distance<=0:
                raise ValueError("invalid sight probe distance")
            eye=(side*float(distance),float(eye_y))
            blockers=[i for i,rect in enumerate(occluders) if segment_crosses_rect(eye,target,rect)]
            probes[f"{'negative_x' if side<0 else 'positive_x'}:{distance:.3f}m"]={
                "eye_xy_m":eye,"target_xy_m":target,"visible":not blockers,
                "occluder_indices":blockers}
    return {"statutory_sight_distance_m":STATUTORY_SIGHT_DISTANCE_M,
            "unobstructed_opposite_width_m":opposite_width,
            "passing_body_collision_frames":collisions,
            "passing_body_outside_paved_frames":outside,
            "physical_passage_observed":not collisions and not outside,
            "sight_probes":probes,
            "legal_adequacy_judgment":"unresolved",
            "district_status":"requires separate administrative source",
            "disability_exception":"requires separate actor and duration evidence"}
