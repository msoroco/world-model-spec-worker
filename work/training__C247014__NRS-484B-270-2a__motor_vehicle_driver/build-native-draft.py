"""Materialize four exact inline Native construction drafts for offline tests."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    source = {name: (HERE / "native" / name).read_text()
              for name in ("runner.py", "scene.py", "finalize.py", "test_scene.py", "test_finalize.py")}
    entries = []
    for suffix in SUFFIXES:
        case = ASSIGNMENT + "__" + suffix
        if case not in {item["case_id"] for item in plan["cases"]}:
            raise ValueError("Frozen planned case identity differs")
        config = {
            "case_id": case, "selected_case_id": case,
            "supported_case_ids": [ASSIGNMENT + "__" + x for x in SUFFIXES],
            "case_suffix": suffix, "candidate_id": "primary",
            "law_id": "NRS-484B-270-2a", "cell_id": "C247014",
            "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
            "cameras": [{"name": name, "width": width, "height": height,
                         "pose_strategy": "survey-gated fixed corridor view", "fov_deg": 85}
                        for name, width, height in CAMERAS],
            "required_atoms": ["ru.bicycle", "ru.motor_vehicle", "kin.position",
                               "kin.heading", "kin.speed", "rel.occupies"],
            "source_packets": [], "case": {"case_id": case},
            "physical_completion": {"criterion": "overtake_pass",
                                    "motion_source": "participant-poses.jsonl",
                                    "body_key": "ego.body_xy_m",
                                    "other_body_key": "cyclist.body_xy_m",
                                    "minimum_progress_m": 1},
            "status": "selected_native_cpu_draft_original_unobserved"}
        recording = {"channels": [
            {"name": name, "unit": "structured", "sampling_rate_hz": 20,
             "method": "original Native actor/frame/lane readback",
             "time_window": "full 600-frame pass", "reference_frame": "Native road",
             "uncertainty": "50 ms sampling; physical and legal review pending"}
            for name in ("ego_pose", "cyclist_pose", "left_lane_occupancy",
                         "drv.overtaking", "drv.lane_change", "rel.occupies")],
            "context_inputs": [{"name": "left_lane_availability", "unit": "source context",
                                "method": "original occupancy and independent review"}],
            "limitations": ["Reasonable safety and due care are not judged by CPU fixtures"]}
        files = [{"path": "runner.py", "content": source["runner.py"]},
                 {"path": "scene.py", "content": source["scene.py"]},
                 {"path": "finalize.py", "content": source["finalize.py"]},
                 {"path": "tests/test_scene.py", "content": source["test_scene.py"]},
                 {"path": "tests/test_finalize.py", "content": source["test_finalize.py"]},
                 {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        proposal = {"case_id": case, "law_id": config["law_id"],
                    "cell_id": config["cell_id"], "actor": config["actor"],
                    "entrypoint": "runner.py", "files": files,
                    "recording_description": recording,
                    "measurement_plan": {"entrypoint": "finalize.py",
                                         "status": "source_bound_saved_finalizer_cpu_tested"},
                    "static_checks": ["two same-direction driving lanes",
                                      "four-camera 600-frame capture",
                                      "left move completes before pass"],
                    "termination_rules": ["600 original frames", "restore owned world"],
                    "mechanisms": ["original Native car/cyclist pose and camera acquisition",
                                   "left-lane occupant in exception_1_2"],
                    "status": "selected_cpu_draft_saved_and_public_proofs_pending"}
        path = HERE / "selected-native-draft" / suffix / "construction.json"
        write(path, proposal)
        entries.append({"case_id": case, "kind": "delivery", "construction": str(path.relative_to(HERE)),
                        "construction_sha256": sha(path),
                        "measurement_contract": suffix + "-measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/diagnostic/" + suffix + "/fixture-recipe.json",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {
                            "status": "physical",
                            "reason": "Original lane transition, cyclist pass and four-view visibility need readback"},
                        "candidates": [], "delivery_readiness": "incomplete"})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(ROOT / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "selected_native_offline_draft", "delivery_ready": False,
                "cases": entries}
    write(HERE / "selected-native-draft-manifest.json", manifest)
    proposal_cases = {"format": "worker-cases-proposal", "cell_id": "C247014",
                      "actor": "motor_vehicle_driver", "status": "draft",
                      "sweep_specs": [], "sweeps_expanded": True, "cases": []}
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[-1]
        construction = json.loads((HERE / "selected-native-draft" / suffix / "construction.json").read_text())
        proposal_cases["cases"].append({"case_id": case["case_id"],
            "target_law_id": "NRS-484B-270-2a", "target_type": "controlled_attempt",
            "rationale": case["physical_target"],
            "variable_assignments": {"comparison_variable": case["comparison_variable"],
                                     "case_suffix": suffix},
            "unresolved_judgment_calls": case["unresolved_judgment_calls"],
            "recording_description": construction["recording_description"]})
    write(HERE / "proposals" / "cases.json", proposal_cases)
    return {"case_count": len(entries), "manifest_sha256": sha(HERE / "selected-native-draft-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
