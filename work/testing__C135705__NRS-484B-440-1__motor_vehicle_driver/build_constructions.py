"""Materialize source-hashed exact primary/fallback Native construction bundles."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
SUFFIXES=("passage_clear_view","passage_blocked","view_occluded_both")


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def description():
    channels=[]
    for name,unit,method in (
        ("standing_body_xy_m","m","Original standing actor eight-vertex box projected to four XY corners at 20 Hz"),
        ("other_vehicle_body_xy_m","m","Original westbound passing actor body, pose and velocity at 20 Hz"),
        ("two_sided_200ft_sight","m and original pixels","Actual prop bodies plus frame-joined cameras at negative and positive 60.96 m"),
        ("mechanical_failure_attempt","command and m","Original worker disable/brake commands joined to standing body and duration")):
        channels.append({"name":name,"unit":unit,"method":method,"sampling_rate_hz":20,
            "time_window":"every original captured frame","reference_frame":"authored OpenDRIVE world XY",
            "uncertainty":"Native body geometry and optical pixels require physical review; no legal cutoff"})
    return {"channels":channels,"context_inputs":[
        {"name":"authored_road","unit":"OpenDRIVE metres","method":"source-hashed candidate paved/shoulder geometry"},
        {"name":"district_review","unit":"administrative source","method":"not supplied; remains unverified"}],
        "limitations":["XY occlusion alone does not establish clear view in original pixels.",
                       "A disable command alone does not establish the subsection (2) exception."]}


def config(scene):
    cid=scene["case_id"]
    return {"law_id":"NRS-484B-440-1","cell_id":"C135705","actor":"motor_vehicle_driver",
        "selected_case_id":cid,"supported_case_ids":[ASSIGNMENT+"__"+s for s in SUFFIXES],
        "rate_hz":20,"duration_s":scene["duration_s"],"required_atoms":[],
        "source_packets":[],"vehicle_blueprint_id":scene["standing_blueprint_id"],
        "cameras":[{"name":name,"width":width,"height":height,"fov_deg":75,
                    "pose_strategy":strategy} for name,width,height,strategy in (
            ("overview",1920,1080,"top down whole road and standing vehicle"),
            ("approach",1280,720,"negative x exact 60.96 m sight toward standing body"),
            ("reference_corner",1280,720,"positive x exact 60.96 m sight toward standing body"),
            ("driver_reference",1280,720,"westbound passing route body view"))],
        "case":{"physical_target":cid.rsplit("__",1)[1],
                "recording_description":description(),
                "sight_probe_distances_m":scene["sight_probe_distances_m"]},
        "physical_completion":{"format":"worker-physical-completion-criteria",
            "criterion":"travel_progress","motion_source":"passing-body-history.jsonl",
            "body_key":"body_vertices_xy_m","minimum_progress_m":10,
            "minimum_samples":3,"direction_xy":[-1,0],
            "engineering_tolerances_not_legal":True}}


def _file(path,source=None,content=None):
    if content is None:
        content=Path(source).read_text() if source else Path(path).read_text()
    entry={"path":path,"content":content}
    if source:entry["source"]=str(Path(source).relative_to(ROOT))
    return entry


def construction(scene,scene_path,contract_path,bundle_scene_path,config_path):
    bundle_scene=copy.deepcopy(scene);bundle_scene["map_source"]="road.xodr"
    cfg=config(bundle_scene)
    files=[]
    for name in ("runner.py","native_construction.py","native_capture.py",
                 "standing_geometry.py","saved_measurement.py","analysis.py",
                 "delivery_audit.py","comparison_audit.py"):
        files.append(_file(name,HERE/name))
    files.extend((_file("road.xodr",HERE/"candidate-standing-road.xodr"),
                  _file("scene.json",bundle_scene_path),
                  _file("config.json",config_path),
                  _file("measurement-contract.json",contract_path),
                  _file("tests/test_offline.py",HERE/"offline_test.py")))
    return {"law_id":"NRS-484B-440-1","cell_id":"C135705","actor":"motor_vehicle_driver",
        "case_id":scene["case_id"],"entrypoint":"runner.py","files":files,
        "measurement_plan":{"standing_passage_two_sided_sight_measurement":
            "Join every original frame to both full-body actors, actual occluder bodies and two exact 60.96 m views; no legal verdict."},
        "recording_description":description(),"static_checks":[
            "source SHA and authored OpenDRIVE lanes/shoulders", "exact case identity",
            "four original 20 Hz cameras","actual standing, passing and occluder actors"],
        "termination_rules":{"duration_s":scene["duration_s"],
            "early_termination":"reject and retain unsealed failure; no fabricated continuation"},
        "mechanisms":["source-hashed two-way candidate OpenDRIVE with explicit shoulders",
            "stationary worker-disabled vehicle with original body and brake history",
            "westbound moving vehicle with original full-body trajectory",
            "real occluder props and both exact 200-foot approach cameras"],
        "source_scene_sha256":sha(scene_path),"source_map_sha256":scene["map_source_sha256"],
        "measurement_contract_sha256":sha(contract_path)}


def main():
    for suffix in SUFFIXES:
        folder=HERE/"cases"/suffix
        contract=folder/"measurement-contract.json"
        for candidate,source_name,target_name in (("primary","scene.json","construction.json"),
                                                   ("fallback1","fallback1-scene.json","fallback1-construction.json")):
            source=folder/source_name;scene=json.loads(source.read_text())
            bundled=copy.deepcopy(scene);bundled["map_source"]="road.xodr"
            bundle_scene_path=folder/("bundle-scene.json" if candidate=="primary" else "fallback1-bundle-scene.json")
            bundle_scene_path.write_text(json.dumps(bundled,indent=2,sort_keys=True)+"\n")
            config_path=folder/"config.json"
            config_path.write_text(json.dumps(config(bundled),indent=2,sort_keys=True)+"\n")
            packet=construction(scene,source,contract,bundle_scene_path,config_path)
            packet["candidate_id"]=candidate
            write(folder/target_name,packet)
        if suffix==SUFFIXES[0]:
            (HERE/"config.json").write_text(json.dumps(
                config(json.loads((folder/"scene.json").read_text())),indent=2,sort_keys=True)+"\n")
            write(HERE/"construction.json",json.loads((folder/"construction.json").read_text()))
    plan_path=HERE/"case-plan.json";plan=json.loads(plan_path.read_text())
    plan["camera_plan"]={"profile":"overview1080-capability","duration_s":9,
        "composition":"synchronized_four_view_primary",
        "coverage":[{"view":view,"subject":subject,"interval":"all 180 original frames at 20 Hz"}
            for view,subject in (("overview","paved road, shoulders, standing and passing body"),
                ("approach","stopped body from negative x 200 feet"),
                ("reference_corner","stopped body from positive x 200 feet"),
                ("driver_reference","westbound other vehicle passage"))]}
    plan["source_observation_mapping"]={}
    for entry in plan["cases"]:entry["status"]="native_source_bound_construction_and_saved_audits_cpu_tested_physical_pending"
    for entry in plan["comparisons"]:entry["status"]="saved_comparison_audit_implemented_diagnostic_proof_pending"
    plan["planning_status"]="three_exact_native_constructions_and_fallbacks_cpu_tested_delivery_proofs_pending"
    write(plan_path,plan)
    print("three primary and three risk-based fallback source-bound constructions")


if __name__=="__main__":main()
