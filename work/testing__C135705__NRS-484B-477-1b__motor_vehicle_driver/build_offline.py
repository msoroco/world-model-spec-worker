"""Materialize exact C135705 primary and reverse-direction fallback bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
AID=HERE.name
VIEWS=(("overview",1920,1080,"connected alley and moving bodies"),
       ("approach",1280,720,"ego approach, park, hold and departure"),
       ("reference_corner",1280,720,"surveyed alley cross sections and body footprints"),
       ("driver_reference",1280,720,"available-width scene from driver reference"))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan_bytes=(HERE/"case-plan.json").read_bytes()
    plan=json.loads(plan_bytes)
    names=[row["name"] for row in plan["observations"]]
    channels=[{"name":name,"unit":"ft" if name=="available_continuous_width_ft" else "structured original source",
               "method":row["source"],"sampling_rate_hz":20,"time_window":"all 900 original Native frames",
               "reference_frame":"surveyed alley cross sections and original Native frame map",
               "uncertainty":"free movement, ordinance and legal interpretation pending"}
              for name,row in zip(names,plan["observations"])]
    description={"channels":channels,"context_inputs":[{"name":"reviewed_alley_width_packet",
        "unit":"source","method":"source-hashed reviewed site, ordinance and actual Native readback"}],
        "limitations":["A constructed width target is not observed free vehicular movement.",
                       "Local ordinance and qualifying other-alley status require independent review."]}
    files=("runner.py","native_capture.py","finalize_native.py","parking_controller.py",
           "alley_width_construction.py","width_measurement.py","analysis.py","case-plan.json",
           "tests/test_bundle.py")
    content={name:(HERE/name).read_text() for name in files}
    base={"assignment_id":AID,"law_id":plan["law_id"],"cell_id":plan["cell_id"],
          "actor":plan["actor"],"rate_hz":20,"frame_count":900,"duration_s":45,
          "required_atoms":[],"source_packets":[],"source_requirements":[
              "source-hashed reviewed qualifying other-alley and jurisdiction/ordinance packet",
              "actual ego and other-vehicle body polygons and provenance",
              "900 original 20 Hz frames and four-camera PNG streams"],
          "supported_case_ids":[row["case_id"] for row in plan["cases"]],
          "cameras":[{"name":name,"width":width,"height":height,"fov_deg":75,
                      "pose_strategy":pose} for name,width,height,pose in VIEWS],
          "recording_description":description,"diagnostic_only":True,
          "plan_sha256":hashlib.sha256(plan_bytes).hexdigest()}
    entries=[]
    for case in plan["cases"]:
        case_id=case["case_id"]
        slug=case_id.removeprefix(AID+"__")
        for candidate,direction in (("primary",1),("fallback1",-1)):
            config=dict(base,selected_case_id=case_id,variant=slug,
                        approach_direction=direction,
                        target_width_ft={"width_9_9ft":9.9,"width_10_0ft":10.0,
                            "width_10_1ft":10.1,"ordinance_otherwise":9.9}.get(slug))
            config['case']={'case_id':case_id,'recording_description':description}
            file_content=dict(content,**{"config.json":json.dumps(config,sort_keys=True,indent=2)+"\n"})
            construction={"law_id":plan["law_id"],"cell_id":plan["cell_id"],
                 "actor":plan["actor"],"case_id":case_id,"entrypoint":"runner.py",
                 "recording_description":description,
                 "measurement_plan":{"case_id":case_id,"procedure":"analysis.py",
                     "source_packets":["alley_geometry","width_history","frame_map"],
                     "free_movement_judgment":"unresolved"},
                 "static_checks":["exact law and case identity","reviewed connected other-alley source and ordinance status",
                                  "actual map, ego and other-vehicle readback","900 original frames and four cameras"],
                 "termination_rules":["900 original Native ticks at 20 Hz","fail closed on absent parked hold or source"],
                 "mechanisms":["source-surveyed lateral parking target","actual other-vehicle close/far spawn target",
                               "route-tracking stop/hold/depart controller","original body and camera acquisition"],
                 "files":[{"path":name,"content":value} for name,value in file_content.items()]}
            relative=Path("cases")/slug/("construction.json" if candidate=="primary" else "fallback1/construction.json")
            path=HERE/relative;write(path,construction)
            if not entries and candidate=="primary":
                write(HERE/"config.json",config)
                write(HERE/"construction.json",construction)
            if candidate=="primary":
                entries.append({"case_id":case_id,"kind":"delivery","construction":str(relative),
                    "construction_sha256":sha(path),"candidate_risk":case["candidate_risk"],
                    "measurement_procedure":{"entrypoint":"analysis.py",
                        "method":"source-bound continuous original alley width and independent free-movement review"},
                    "acquisition":{name:{"entrypoint":"analysis.py","method":"original Native source join",
                        "evidence":"channels/"+name+".jsonl"} for name in names},
                    "native_handoff":{"python_env_var":"CARLA_PYTHON","host_env_var":"CARLA_HOST",
                                      "port_env_var":"CARLA_PORT"},"candidates":[]})
            else:
                entries[-1]["candidates"].append({"id":"fallback1","construction":str(relative),
                    "construction_sha256":sha(path),
                    "changed_knobs":["reverse surveyed connected-alley approach direction, preserving parking and width targets"],
                    "trigger":{"source":"original Native actor, body width and four-camera history",
                        "metric":"parked target width and complete camera coverage",
                        "failure_condition":"primary approach fails to realize the parked target or full visibility"}})
    write(HERE/"execution-manifest.json",{"format":"worker-execution-manifest",
        "assignment_id":AID,"runtime_manifest_sha256":sha(REPO/"runtime/SOURCE-MANIFEST.json"),
        "cases":entries})
    return len(entries)


if __name__=='__main__':print(build())
