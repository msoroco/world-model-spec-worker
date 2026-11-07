"""Measure three isolated fallback crossings from source-hashed synthetic inputs."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE / "native"))
from traversal import pose

SOURCE=HERE / "traversal-cpu/trigger-source.json"
OUTPUT=HERE / "traversal-cpu/trigger-summary.json"
CASES=("traversal_reference","traversal_contrast")


def metrics(row):
    route=row["route_xy_m"]
    actual=row["observed_xy_m"]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in route+actual):
        raise ValueError("Nonfinite route observation")
    speed=row["parking_endpoint_speed_m_s"]
    if type(speed) not in (int,float) or not math.isfinite(speed) or speed<0:
        raise ValueError("Invalid observed parking speed")
    left,top,right,bottom=row["ego_bbox_px"]
    if not (0<=left<right<=1920 and 0<=top<bottom<=1080):
        raise ValueError("Invalid synthetic ego pixel box")
    return {"max_route_cross_track_error_m":math.dist(route,actual),
            "parking_endpoint_speed_m_s":speed,
            "min_ego_pixel_margin_px":min(left,top,1920-right,1080-bottom)}


def main():
    definitions={"baseline":(0.2,0.1,80),"route_error":(0.8,0.1,80),
                 "parking_speed":(0.2,0.8,80),"pixel_margin":(0.2,0.1,20)}
    rows=[]
    for case in CASES:
        x,y=pose(case,333)
        for scenario,(route_error,parking_speed,margin) in definitions.items():
            rows.append({"case":case,"scenario":scenario,"route_xy_m":[x,y],
                         "observed_xy_m":[x,y+route_error],
                         "parking_endpoint_speed_m_s":parking_speed,
                         "ego_bbox_px":[margin,margin,1920-margin,1080-margin]})
    source={"source_kind":"synthetic_cpu_measurement_fixture",
            "original_native_observed":False,"original_pixels_observed":False,
            "measurements":rows}
    SOURCE.write_text(json.dumps(source,indent=2,allow_nan=False)+"\n")
    decisions=[]
    for row in rows:
        observed=metrics(row)
        decisions.append({"case":row["case"],"scenario":row["scenario"],
            "metrics":observed,
            "fallback1_trigger":observed["max_route_cross_track_error_m"]>.45,
            "fallback2_trigger":observed["parking_endpoint_speed_m_s"]>.3,
            "fallback3_trigger":observed["min_ego_pixel_margin_px"]<40})
    for case in CASES:
        by={d["scenario"]:d for d in decisions if d["case"]==case}
        if any(by["baseline"]["fallback"+str(i)+"_trigger"] for i in (1,2,3)):
            raise ValueError("Baseline fallback triggered")
        for scenario,number in (("route_error",1),("parking_speed",2),("pixel_margin",3)):
            if [by[scenario]["fallback"+str(i)+"_trigger"] for i in (1,2,3)] != [i==number for i in (1,2,3)]:
                raise ValueError("Fallback threshold crossing not isolated")
    output={"source_kind":"synthetic_cpu_measurement_fixture",
            "source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "original_native_observed":False,"original_pixels_observed":False,
            "decisions":decisions}
    OUTPUT.write_text(json.dumps(output,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"cases":2,"measured_rows":len(rows),"isolated_crossings_per_case":3}))


if __name__=="__main__":main()
