"""Authored same-cell intersection parking probes for LVMC 11.52.130(A)(11)."""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOUNDARY_X_M = 7.0
FIFTEEN_FEET_M = 15 * .3048
PARK_STATIONS_M = {"witness_1": 25.0, "witness_2": 13.5,
                   "numeric_1_0": 13.5, "numeric_1_1": 14.172,
                   "numeric_1_2": 15.0}
BODY_HALF_LENGTH_M = 2.6
BODY_HALF_WIDTH_M = 1.1


def route(case: str) -> list[list[float]]:
    if case not in PARK_STATIONS_M:
        raise ValueError("Unknown parking probe")
    stop = PARK_STATIONS_M[case]
    shift_start = stop - 4.0 if case != "witness_1" else stop - 7.0
    shift_end = shift_start + 4.0
    points = []
    for index in range(round((stop + 70) * 20) + 1):
        x = round(-70 + index * .05, 4)
        if x <= shift_start:
            y = -1.75
        elif x >= shift_end:
            y = -5.25
        else:
            t = (x - shift_start) / 4
            y = -1.75 - 3.5 * t*t*(3-2*t)
        points.append([x, round(y, 6)])
    if points[-1][0] != stop:
        points.append([stop, -5.25])
    return points


def body(x, y):
    return ((x-2.6,y-1.1),(x-2.6,y+1.1),
            (x+2.6,y+1.1),(x+2.6,y-1.1))


def check():
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    road = HERE / "road.xodr"
    if not road.is_file():
        raise ValueError("Authored same-cell road is missing")
    pavement = unary_union((box(-100,-3.5,100,3.5),
                            box(-3.5,-100,3.5,100),
                            box(8,-7,35,-3.5)))
    result = {}
    for case in PARK_STATIONS_M:
        points = route(case)
        if max(math.dist(a,b) for a,b in zip(points,points[1:])) > .15:
            raise ValueError("Parking path discontinuity")
        for x,y in points:
            if not pavement.covers(Polygon(body(x,y))):
                raise ValueError("Prospective body leaves authored pavement")
        x,y = points[-1]
        if y != -5.25:
            raise ValueError("Probe did not reach parking bay")
        nearest = (x - BODY_HALF_LENGTH_M) - BOUNDARY_X_M
        relation=("boundary_unresolved" if abs(nearest-FIFTEEN_FEET_M)<.05 else
                  "within_15_ft" if nearest<FIFTEEN_FEET_M else "outside_15_ft")
        result[case] = {"stop_center_x_m":x,"nearest_body_to_intersection_m":round(nearest,4),
                        "within_15_ft_proposed":None if relation=="boundary_unresolved" else relation=="within_15_ft",
                        "sampled_relation":relation,
                        "route_points":len(points),"parking_y_m":y}
    if result["witness_1"]["within_15_ft_proposed"] or not result["witness_2"]["within_15_ft_proposed"]:
        raise ValueError("Controlled parking stations do not bracket statutory band")
    return {"passed":True,"scope":"authored route and prospective body only",
            "law_id":"LVMC-11-52-130-A11","cell_id":"C110454",
            "fifteen_feet_m":FIFTEEN_FEET_M,"intersection_entry_boundary_x_m":BOUNDARY_X_M,
            "case_results":result,"native_observed":False,"legal_verdict":None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-routes",action="store_true")
    args=parser.parse_args()
    result=check()
    if args.write_routes:
        routes=HERE/"routes"; routes.mkdir(exist_ok=True)
        for case in PARK_STATIONS_M:
            (routes/(case+".json")).write_text(json.dumps(route(case)))
    print(json.dumps(result,sort_keys=True))
