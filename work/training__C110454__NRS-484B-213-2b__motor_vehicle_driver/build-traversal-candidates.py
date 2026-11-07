"""Build eight exact, unselected C110454 intersection traversal bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
sys.path.insert(0,str(NATIVE))
from engineering import BASE, CHANGES, TRIGGERS
from traversal import check_pair

CASES = ("traversal_reference","traversal_contrast")
CANDIDATES = ("primary","fallback1","fallback2","fallback3")
FILES = {"runner.py":"runner_traversal.py","runner_base.py":"runner.py",
         "geometry.py":"geometry.py","traversal.py":"traversal.py",
         "controller.py":"controller.py","engineering.py":"engineering.py",
         "cameras.py":"cameras.py","finalize.py":"finalize_traversal.py",
         "finalize_base.py":"finalize.py","measure.py":"measure.py"}
TESTS = ("test_runner.py","test_bundle_engineering.py","test_bundle_traversal.py")


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+"\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recording():
    names = ("drv.approaching","drv.in_intersection","st.intersection",
             "st.railway_crossing","st.centre_line","rel.occupies",
             "kin.position","rel.centre_distance","st.one_way_roadway",
             "native_body_pose_control","camera_frame_join")
    return {"channels":[{"name":name,"unit":"structured","sampling_rate_hz":20,
             "method":"Original Native map, full body, velocity and synchronized video frame",
             "time_window":"original 24 s / 480 frame attempt",
             "reference_frame":"surveyed two-way Native map and original frame",
             "uncertainty":"50 ms samples; original physical map and pixels require capture"}
             for name in names],
        "context_inputs":[{"name":"surveyed_two_way_intersection","unit":"structured",
            "method":"Native OpenDRIVE readback and lane direction survey"}],
        "limitations":["CPU fixture does not establish physical behavior or legal verdict"]}


def main():
    check_pair()
    batch = json.loads((ROOT / "batch.json").read_text())
    shared = [{"path":dest,"content":(NATIVE / src).read_text()} for dest,src in FILES.items()]
    shared += [{"path":"tests/" + name,"content":(NATIVE / name).read_text()} for name in TESTS]
    description = recording()
    manifest = {"format":"worker-unselected-draft-construction-manifest-v1",
        "assignment_id":HERE.name,
        "runtime_manifest_sha256":batch["runtime"]["source_manifest_sha256"],
        "status":"draft_not_selected","scope":"intersection traversal source alternative; no legal verdict",
        "cases":[]}
    proposals = []
    for suffix in CASES:
        case_id = HERE.name + "__" + suffix
        entry = {"case_id":case_id,"kind":"draft_not_selected",
            "candidate_risk":{"status":"physical",
                "reason":"Native route tracking, full-body intersection traversal, parking and original pixels require physical capture"},
            "measurement_contract":f"draft-traversal-contracts/{suffix}/measurement-contract.json",
            "measurement_procedure":{"entrypoint":"finalize.py","output_schema":"c110454-traversal-saved-analysis-v1"},
            "candidates":[]}
        proposals.append({"case_id":case_id,"target_law_id":"NRS-484B-213-2b",
            "target_type":"attempt","recording_description":description})
        write(HERE / "draft-traversal-contracts" / suffix / "measurement-contract.json",
            {"format":"worker-measurement-contract-v1","case_id":case_id,
             "requirements":[
                {"disposition_index":0,"requirement":"text-0",
                 "source":"inputs/coverage/branch-sources.json",
                 "output_key":"left_side_traversal","method":"measure_traversal",
                 "value_type":"boolean","kind":"measured",
                 "inputs":["native_samples.jsonl","road_geometry.json"]},
                {"disposition_index":1,"requirement":"text-1",
                 "source":"inputs/coverage/branch-sources.json",
                 "output_key":"intersection_traversal","method":"measure_traversal",
                 "value_type":"object","kind":"measured",
                 "inputs":["native_samples.jsonl","road_geometry.json"]}],
             "negative":{"remove":["native_samples.jsonl"],
                 "error_contains":"Missing required source: native_samples.jsonl"},
             "scope":"saved sampled full body and Native polygon; not a legal verdict"})
        for candidate in CANDIDATES:
            knobs = BASE | CHANGES[candidate]
            config = {"case_id":case_id,"selected_case_id":case_id,
                "supported_case_ids":[case_id],"case":{"case_id":case_id},
                "case_suffix":suffix,"candidate_id":candidate,
                "cell_id":"C110454","law_id":"NRS-484B-213-2b",
                "actor":"motor_vehicle_driver","duration_s":24,"rate_hz":20,
                "required_atoms":["drv.in_intersection","st.intersection",
                    "st.centre_line","rel.occupies","kin.position"],
                "source_packets":[],"mandatory_channels":[c["name"] for c in description["channels"]],
                "recording_description":description,
                "cameras":[{"name":name,"width":width,"height":height} for name,width,height in
                    (("overview",1920,1080),("approach",1280,720),
                     ("intersection",1280,720),("parking",1280,720))],
                "engineering_knobs":knobs,"status":"unselected_native_runner_prototype"}
            files = shared + [{"path":"config.json","content":json.dumps(config,indent=2)+"\n"}]
            construction = {"case_id":case_id,"cell_id":"C110454",
                "law_id":"NRS-484B-213-2b","actor":"motor_vehicle_driver",
                "entrypoint":"runner.py","files":files,"recording_description":description,
                "measurement_plan":{"method":"saved moving full body inside Native two-way intersection polygon",
                    "status":"unselected_cpu_proposal"},
                "static_checks":["authored traversal route pair and full-body pavement",
                    "source-bound saved-frame traversal measure","four-view 480-frame contract"],
                "termination_rules":["full 480 original frames","capture or restoration failure retained"],
                "mechanisms":["two-way intersection","observed-pose route controller",
                    "four synchronized lossless cameras"],"status":"unselected_cpu_draft"}
            path = HERE / "draft-traversal-candidates" / suffix / candidate / "construction.json"
            write(path,construction)
            ref = {"id":candidate,"construction":str(path.relative_to(HERE)),
                   "construction_sha256":sha(path)}
            if candidate == "primary":
                entry.update(ref)
            else:
                trigger = TRIGGERS[candidate]
                ref["trigger"] = trigger | {"failure_condition":f'{trigger["metric"]} {trigger["op"]} {trigger["threshold"]}'}
                ref["changed_knobs"] = list(CHANGES[candidate])
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    write(HERE / "draft-traversal-execution-manifest.json",manifest)
    source = HERE / "proposals/cases.json"
    existing = json.loads(source.read_text())
    ids = {c["case_id"] for c in proposals}
    existing["cases"] = [c for c in existing["cases"] if c["case_id"] not in ids] + proposals
    write(source,existing)
    print(json.dumps({"cases":len(manifest["cases"]),"candidates":8}))


if __name__ == "__main__":
    main()
