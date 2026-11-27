"""Bind exact two-case yield-crosswalk Native bundles to frozen sources."""

import hashlib
import json
from pathlib import Path

from yield_crosswalk_scene import CASES, request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
MODULES = ("yield_crosswalk_scene.py", "native_construction.py", "native_capture.py",
           "measure_yield_crosswalk.py", "finalize.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def description():
    return {"channels": [{"name": "ego_pose", "unit": "m,deg",
        "sampling_rate_hz": 20, "method": "original Native ego transform and full body extent joined to each frame",
        "time_window": "all 600 frames, including first rest and crossing",
        "reference_frame": "original CARLA XY and Native frame",
        "uncertainty": "50 ms sampling; original pixels and body visibility need independent review"},
        {"name": "conditional_stop_position", "unit": "m,m/s",
        "sampling_rate_hz": 20,
        "method": "first recorded rest front-bumper extent versus original near-side crosswalk edge",
        "time_window": "all 600 frames through intersection entry",
        "reference_frame": "source-hashed original map crosswalk and vehicle body",
        "uncertainty": "0.1 m/s rest diagnostic; no legal safety threshold or compliance judgment"}],
        "context_inputs": [{"name": name, "unit": "structured",
            "method": "original Native source hash and per-frame identity join"}
            for name in ("governing_yield_sign", "near_side_crosswalk", "intersecting_traffic", "safety_context")],
        "limitations": ["Whether safety required a stop is an unresolved independent judgment.",
                        "Authored stop request and synthetic fixture do not prove physical stopping or legal compliance."]}


def config(slug):
    scene = request(slug)
    cid = AID + "__" + slug
    record = description()
    return {"assignment_id": AID, "law_id": "NRS-484A-450-3", "cell_id": "C111343",
        "actor": "motor_vehicle_driver", "selected_case_id": cid,
        "case": {"case_id": cid, "recording_description": record},
        "supported_case_ids": [AID + "__" + key for key in CASES],
        "required_atoms": [], "source_packets": [], "rate_hz": 20, "duration_s": 30,
        "frames": 600, "requested_stop_before_crosswalk": slug == "before_crosswalk",
        "requested_stop_front_x_m": scene["controller"]["requested_stop_front_x_m"],
        "cameras": [{"name": item["name"], "width": item["size"][0],
            "height": item["size"][1], "fps": 20, "fov_deg": 80,
            "pose_strategy": item["pose_strategy"]} for item in scene["cameras"]],
        "recording_description": record, "physical_acceptance_claimed": False,
        "legal_verdict": None, "safety_stop_required": "unassessed"}


def build(slug):
    if slug not in CASES:
        raise ValueError("Unknown exact case")
    cid = AID + "__" + slug
    frozen = REPO / "inputs" / AID / "assignment.json"
    assignment = json.loads(frozen.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if (assignment["law"]["text"] != plan["source_law_text"] or
            assignment["cell"]["control"] != "yield_sign" or
            assignment["cell"]["maneuver"] != "travel" or
            assignment["cell"]["layout"] != "intersection"):
        raise ValueError("Frozen law or yield-sign cell differs")
    cfg = config(slug)
    contract = {"format": "worker-measurement-contract", "case_id": cid,
        "status": "selected_cpu_draft", "negative": {"remove": ["near_crosswalk.json"],
            "error_contains": "Missing required source: near_crosswalk.json"},
        "requirements": [
            {"disposition_index": i, "requirement": disposition["requirement"],
             "source": disposition["source"], "kind": "measured",
             "method": "measure_crosswalk_position" if i == 0 else "measure_yield_governance",
             "output_key": "crosswalk_stop_position" if i == 0 else "conditional_yield_context",
             "value_type": "object",
             "inputs": ["near_crosswalk.json", "ego_body.jsonl", "yield_motion.jsonl",
                        "video_frames.jsonl"] if i == 0 else
                       ["yield_sign.json", "intersecting_traffic.json", "safety_context.json",
                        "yield_motion.jsonl"]}
            for i, disposition in enumerate(plan["requirement_dispositions"])],
        "legal_compliance": "unassessed"}
    contract_path = HERE / ("measurement-" + slug + ".json")
    put(contract_path, contract)
    files = [{"path": "runner.py", "source": str((HERE / "runner.py").relative_to(REPO)),
              "content": (HERE / "runner.py").read_text()}]
    for name in MODULES:
        path = HERE / name
        files.append({"path": name, "source": str(path.relative_to(REPO)),
                      "content": path.read_text()})
    files += [{"path": "config.json", "content": json.dumps(cfg, indent=2) + "\n"},
              {"path": "inputs/" + AID + "/assignment.json", "content": frozen.read_text()},
              {"path": "work/" + AID + "/case-plan.json",
               "content": (HERE / "case-plan.json").read_text()}]
    for name in ("test_native_construction.py",):
        path = HERE / name
        files.append({"path": "tests/" + name, "source": str(path.relative_to(REPO)),
                      "content": path.read_text()})
    construction = {"case_id": cid, "law_id": "NRS-484A-450-3", "cell_id": "C111343",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
        "status": "selected_cpu_prepared_original_unverified",
        "recording_description": cfg["recording_description"],
        "measurement_plan": {"method": "source-body first rest relative to original near-side crosswalk",
            "duration_s": 30, "source_observation_channels": ["ego_pose", "conditional_stop_position",
                "governing_yield_sign", "near_side_crosswalk", "intersecting_traffic", "safety_context"]},
        "static_checks": ["governing YIELD sign and near-side crosswalk map readback",
                          "two spawned vehicles", "four original 20 Hz cameras", "600 frame joins"],
        "termination_rules": ["600 frames", "source camera encoder closure and world restore"],
        "mechanisms": ["CARLA OpenDRIVE intersection and crosswalk object",
                       "independently controlled ego and intersecting vehicle",
                       "source-joined four-view FFV1 and Native telemetry"]}
    path = HERE / "selected" / slug / "construction.json"
    put(path, construction)
    fallback = json.loads(json.dumps(construction))
    fallback_config = dict(cfg)
    fallback_config["requested_stop_front_x_m"] = -10.0 if slug == "before_crosswalk" else -5.0
    for item in fallback["files"]:
        if item["path"] == "config.json":
            item["content"] = json.dumps(fallback_config, indent=2) + "\n"
    fallback_path = HERE / "selected" / slug / "fallback1-construction.json"
    put(fallback_path, fallback)
    return {"case_id": cid, "kind": "delivery",
            "construction": str(path.relative_to(HERE)), "construction_sha256": sha(path),
            "measurement_procedure": {"entrypoint": "finalize.py"},
            "measurement_contract": contract_path.name,
            "fixture_recipe": "work/" + AID + "/selected-recipe-" + slug + ".json",
            "recording_description": cfg["recording_description"],
            "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "candidate_risk": {"status": "physical",
                "reason": "Actual brake tracking near the crosswalk or four-camera visibility may fail"},
            "candidates": [{"id": "fallback1", "construction": str(fallback_path.relative_to(HERE)),
                "construction_sha256": sha(fallback_path),
                "changed_knobs": ["requested_stop_front_x_m: " + str(cfg["requested_stop_front_x_m"])
                                  + " to " + str(fallback_config["requested_stop_front_x_m"])],
                "trigger": {"source": "original saved ego_body.jsonl and near_crosswalk.json",
                    "metric": "first rest full-body front-bumper x versus near-side crosswalk edge",
                    "failure_condition": "Primary requested rest is not physically realized or body visibility is inadequate"}}]}


def main():
    entries = [build(slug) for slug in CASES]
    batch = json.loads((REPO / "batch.json").read_text())
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
        "status": "draft_incomplete_proofs", "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
        "physical_acceptance_claimed": False, "cases": entries}
    put(HERE / "draft-native-manifest.json", manifest)
    put(HERE / "config.json", config("before_crosswalk"))
    (HERE / "construction.json").write_bytes((HERE / entries[0]["construction"]).read_bytes())
    return {"cases": len(entries), "manifest_sha256": sha(HERE / "draft-native-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
