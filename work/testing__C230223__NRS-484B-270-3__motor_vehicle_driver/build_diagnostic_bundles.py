"""Bind every exact selected case to its own inline CPU construction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan=json.loads((ROOT/"case-plan.json").read_text())
    base_config=json.loads((ROOT/"config.json").read_text())
    names=("runner.py","cycle_lane_2703.py","cycle_lane_native.py",
           "analysis.py","case-plan.json","tests/test_bundle.py")
    channels=[{"name":name,"unit":unit,"sampling_rate_hz":20,
               "method":"Original synchronized Native body/control readback",
               "time_window":"full 45-second episode","reference_frame":"original Native world",
               "uncertainty":"physical source review pending"}
              for name,unit in (("ego_body_polygon","Native world XY"),
                                ("participant_body_polygon","Native world XY"),
                                ("ego_lane_occupancy","boolean"),
                                ("participant_lane_occupancy","boolean"),
                                ("ego_control","CARLA control"),
                                ("participant_control","CARLA control"))]
    description={"channels":channels,"context_inputs":[
        {"name":name,"unit":"reviewed source packet","method":"SHA-256 bound original source review"}
        for name in ("site_designation","participant_identity","exception_context",
                     "pedestrian_qualification")],
        "limitations":["Synthetic fixture establishes software shape only.",
                       "Actual participant behavior, camera pixels and legal judgment require independent original review."]}
    source_files=("site-source.json","participant-source.json","context-source.json","history.json")
    manifest={"assignment_id":plan["assignment_id"],"status":"diagnostic_unselected",
              "physical_acceptance_claimed":False,
              "runtime_manifest_sha256":json.loads((REPO/"batch.json").read_text())["runtime"]["source_manifest_sha256"],
              "cases":[],"comparisons":plan["comparisons"]}
    for number,case in enumerate(plan["cases"]):
        slug=case["case_slug"]
        folder=ROOT/"cases"/slug
        config=dict(base_config,selected_case_id=case["case_id"],
                    requested_lane_action=case["ego_lane_action_request"],
                    requested_precedence=case["ego_precedence_request"],
                    requested_exception=case["exception_request"],
                    requested_participant_kind=case["road_user_kind"])
        config_text=json.dumps(config,indent=2,ensure_ascii=False)+"\n"
        if number==0:
            (ROOT/"config.json").write_text(config_text)
        write(folder/"config.json",config)
        files=[{"path":name,"content":(ROOT/name).read_text()} for name in names]
        files.append({"path":"config.json","content":config_text})
        construction={"law_id":plan["law_id"],"cell_id":plan["cell_id"],
            "actor":plan["actor"],"case_id":case["case_id"],"diagnostic_only":True,
            "entrypoint":"runner.py","files":files,
            "measurement_plan":["900 original 20 Hz actor/frame joins",
                "source-reviewed facility and actor identity",
                "motor-vehicle and qualifying participant body occupancy",
                "observed conflict-zone precedence and exact lane action",
                "separately reviewed exception or pedestrian qualification context",
                "four-camera full decode and physical/pixel review"],
            "mechanisms":["reviewed OpenDRIVE cycle-facility geometry",
                "distinct source-reviewed participant and physical rider where applicable",
                "source-gated alley/driveway or exceptional circumstance",
                "route-following motor-vehicle and participant controllers",
                "four synchronized original RGB views"],
            "recording_description":description,
            "termination_rules":{"frames":900,"native_sync_required":True},
            "static_checks":["reviewed source packet SHA-256 gate",
                "exact route intersects source facility and conflict zone",
                "all original actor body polygons and 900 frame joins"]}
        write(folder/"construction.json",construction)
        if number==0:
            write(ROOT/"construction.json",construction)
        selected=[i for i,d in enumerate(plan["requirement_dispositions"])
                  if case["case_id"] in d["case_ids"]]
        contract={"format":"worker-measurement-contract",
                  "requirements":[{"disposition_index":i,
                      "requirement":plan["requirement_dispositions"][i]["requirement"],
                      "source":plan["requirement_dispositions"][i]["source"],
                      "output_key":f"cycle_lane_2703_requirement_{i}",
                      "method":"measure_saved","value_type":"object","kind":"measured",
                      "inputs":list(source_files)} for i in selected],
                  "negative":{"remove":["context-source.json"],
                              "error_contains":"Missing required source: context-source.json"}}
        write(folder/"measurement-contract.json",contract)
        if number==0:
            write(ROOT/"measurement-contract.json",contract)
        manifest["cases"].append({"case_id":case["case_id"],
            "kind":"diagnostic_unselected",
            "construction":f"cases/{slug}/construction.json",
            "construction_sha256":sha(folder/"construction.json"),
            "measurement_contract":f"cases/{slug}/measurement-contract.json",
            "measurement_procedure":{"entrypoint":"analysis.py"},
            "fixture_recipe":str((folder/"diagnostic-recipe.json").relative_to(REPO)),
            "candidate_risk":{"status":"none",
                "reason":"Original route/actor visibility is pending; no observed physical failure identifies a safe engineering fallback yet."},
            "candidates":[]})
    write(ROOT/"diagnostic-execution-manifest.json",manifest)
    print("bundled",len(manifest["cases"]),"exact diagnostic constructions")


if __name__=="__main__":
    build()
