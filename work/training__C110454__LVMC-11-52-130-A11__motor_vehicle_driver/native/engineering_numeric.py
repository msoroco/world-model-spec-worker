"""Unselected parking-law fallback knobs and source-bound risk decisions."""
import hashlib
import json
from pathlib import Path

CASES=("numeric_1_0","numeric_1_1","numeric_1_2")
CANDIDATES=("primary","fallback1","fallback2","fallback3")
BASE={"route_lookahead_m":6.0,"parking_brake_start_m":12.0,
      "overview_fov_deg":90.0,"rate_hz":20,"duration_s":24.0,
      "camera_ids":["overview","approach","intersection","parking"]}
DELTA={"primary":{},"fallback1":{"route_lookahead_m":3.5},
       "fallback2":{"parking_brake_start_m":17.0},
       "fallback3":{"overview_fov_deg":105.0}}
TRIGGERS={"fallback1":("max_park_route_cross_track_error_m",">",.45),
          "fallback2":("parked_endpoint_speed_m_s",">",.3),
          "fallback3":("min_parked_ego_pixel_margin_px","<",40)}


def plan(case,candidate):
    if case not in CASES or candidate not in CANDIDATES:raise ValueError("Unknown case/candidate")
    return {"case_suffix":case,"candidate":candidate,"knobs":BASE|DELTA[candidate],
            "measured_trigger":TRIGGERS.get(candidate),"physical_trigger_observed":False}


def parameters(case,candidate):
    return plan(case,candidate)


def controller_parameters(case,candidate):
    from controller import EngineeringKnobs
    knobs=plan(case,candidate)['knobs']
    return EngineeringKnobs(lookahead_base_m=knobs['route_lookahead_m'],
                            target_speed_mps=5.5,
                            final_brake_mps2=1.5,
                            final_margin_m=knobs['parking_brake_start_m']-9.0)


def evaluate(candidate,source:Path,expected_sha256:str):
    if candidate not in TRIGGERS:raise ValueError("No fallback trigger")
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError("Original source hash differs")
    values=json.loads(source.read_text())
    if values.get("source_kind")!="native_video_metrics":
        raise ValueError("Original Native/video metrics missing")
    key,op,threshold=TRIGGERS[candidate]
    value=values.get(key)
    if type(value) not in (int,float):raise ValueError("Measured trigger value missing")
    return value>threshold if op==">" else value<threshold
