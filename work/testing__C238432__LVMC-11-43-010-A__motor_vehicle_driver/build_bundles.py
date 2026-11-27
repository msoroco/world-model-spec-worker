"""Write exact inline direction constructions from one reviewed case plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from direction import ASSIGNMENT, CASE_DIRECTIONS

HERE=Path(__file__).resolve().parent
VIEWS=(("overview",1920,1080),("approach",1280,720),
       ("reference_corner",1280,720),("driver_reference",1280,720))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n")


def recording():
    channels=[]
    for name,unit in (("original_roundabout_topology","source"),
                      ("original_operator_identity","actor"),
                      ("original_ring_trajectory","rad"),
                      ("original_four_camera_pixels","frame")):
        channels.append({"name":name,"unit":unit,"sampling_rate_hz":20,
                         "method":"source-sealed original Native readback",
                         "reference_frame":"original CARLA map XY and original frames",
                         "time_window":"all 900 ticks",
                         "uncertainty":"physical realization pending"})
    return {"channels":channels,"context_inputs":[{"name":"reviewed_roundabout_map",
        "unit":"source","method":"source-hashed active OpenDRIVE and roundabout survey"}],
        "limitations":["Original ring trajectory and map context are measurements; legal judgment remains separate."]}


def bundle(case_id,plan_sha):
    root=HERE if case_id.endswith("__counterclockwise") else HERE/"cases"/"clockwise"
    rec=recording()
    config={"assignment_id":ASSIGNMENT,"law_id":"LVMC-11-43-010-A",
            "cell_id":"C238432","actor":"motor_vehicle_driver",
            "selected_case_id":case_id,"supported_case_ids":list(CASE_DIRECTIONS),
            "duration_s":45,"rate_hz":20,"required_atoms":[],"source_packets":[],
            "plan_sha256":plan_sha,"route_throttle":.32,
            "cameras":[{"name":name,"width":width,"height":height,"fov_deg":80,
                "pose_strategy":"surveyed central island, ring route and original vehicle body"}
                for name,width,height in VIEWS],
            "case":{"case_id":case_id,"physical_target":"original vehicular travel within a roundabout",
                    "recording_description":rec},
            "physical_completion":{"criterion":"travel_progress",
                "motion_source":"trace.jsonl","position_key":"position_m",
                "minimum_samples":3,"minimum_progress_m":1.0,
                "engineering_tolerances_not_legal":True,
                "completion_goal_method":"Original ring arc and motion require independent physical review"}}
    files=[]
    for name in ("runner.py","direction.py","analysis.py","case-plan.json","config.json",
                 "tests/test_direction.py"):
        if name=="config.json":
            content=json.dumps(config,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
        else:
            content=(HERE/name).read_text()
        source=root/name if name=="config.json" else HERE/name
        files.append({"path":name,"source":str(source.relative_to(HERE.parents[1])),"content":content})
    construction={"case_id":case_id,"law_id":"LVMC-11-43-010-A",
                  "cell_id":"C238432","actor":"motor_vehicle_driver",
                  "entrypoint":"runner.py","files":files,
                  "measurement_plan":{"selected_requirement":"LVMC 11.43.010(A)",
                      "saved_method":"Signed original ring arc from source-sealed 20 Hz actor trajectory",
                      "legal_judgment":"unresolved"},
                  "mechanisms":["reviewed source-hashed roundabout map and both routes",
                      "bounded route controller","900 original actor frames","four synchronized RGB cameras"],
                  "recording_description":rec,
                  "static_checks":["exact case and scope","20 Hz four-camera profile",
                      "source-hashed map required before Native motion"],
                  "termination_rules":{"duration_s":45,
                      "early_termination":"Retain failed attempt; never mark as physical completion"}}
    write(root/"config.json",config)
    write(root/"construction.json",construction)
    return root


if __name__=="__main__":
    plan_sha=hashlib.sha256((HERE/"case-plan.json").read_bytes()).hexdigest()
    for case_id in CASE_DIRECTIONS:
        bundle(case_id,plan_sha)
