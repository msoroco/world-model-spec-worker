"""Build source-bound exact case construction drafts for CPU offline checks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2",
            "numeric_1_0", "numeric_1_1", "numeric_1_2", "ordering_1", "ordering_2")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
CHANNELS = ("ego_body", "scooter_body", "body_surface_gap", "left_pass",
            "right_return", "center_marking")
SOURCES = ["participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl",
           "road.xodr", "pass-context.json", "capture/evidence.jsonl"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if {case["case_id"] for case in plan["cases"]} != {AID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("Exact planned cases differ")
    files = {name: (HERE / "native" / name).read_text() for name in
             ("runner.py", "scene.py", "measure.py", "finalize.py",
              "test_scene.py", "test_measure.py", "test_finalize.py")}
    entries = []
    proposal_cases = {"format": "worker-cases-proposal", "cell_id": "C272412",
                      "actor": "motor_vehicle_driver", "status": "draft",
                      "sweep_specs": [], "sweeps_expanded": True, "cases": []}
    for suffix in SUFFIXES:
        case = AID + "__" + suffix
        planned = next(item for item in plan["cases"] if item["case_id"] == case)
        recording = {"channels": [{"name": name, "unit": "original-source-derived",
                                    "sampling_rate_hz": 20,
                                    "method": "saved original actor/body, frame and road readback",
                                    "time_window": "full 600-frame pass",
                                    "reference_frame": "Native road",
                                    "uncertainty": "50 ms samples; between-frame gap and legal safety unverified"}
                                   for name in CHANNELS],
                     "context_inputs": [{"name": "source_review", "unit": "source context",
                                         "method": "original scooter survey and cited-law operator review"}],
                     "limitations": ["Sampled body gap is not continuous physical clearance",
                                     "No judgment of due care, safely clear or safe center crossing"]}
        config = {"case_id": case, "selected_case_id": case,
                  "supported_case_ids": [AID + "__" + s for s in SUFFIXES],
                  "case_suffix": suffix, "candidate_id": "primary",
                  "law_id": "NRS-484B-270-2b", "cell_id": "C272412",
                  "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
                  "cameras": [{"name": name, "width": width, "height": height,
                               "pose_strategy": "survey-gated fixed corridor view", "fov_deg": 85}
                              for name, width, height in CAMERAS],
                  "required_atoms": ["ru.motor_vehicle",
                                     "kin.position", "kin.heading", "kin.speed",
                                     "rel.surface_gap", "st.lane_adjacency"],
                  "source_packets": [], "case": {"case_id": case,
                                                  "recording_description": recording},
                  "physical_completion": {"criterion": "overtake_pass",
                                          "motion_source": "participant-poses.jsonl",
                                          "body_key": "ego.body_xy_m",
                                          "other_body_key": "scooter.body_xy_m",
                                          "minimum_progress_m": 1},
                  "physical_acceptance_claimed": False,
                  "legal_verdict": None}
        inline = [{"path": name, "content": files[name]} for name in
                  ("runner.py", "scene.py", "measure.py", "finalize.py")]
        inline += [{"path": "tests/" + name, "content": files[name]} for name in
                   ("test_scene.py", "test_measure.py", "test_finalize.py")]
        inline.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        proposal = {"case_id": case, "law_id": config["law_id"], "cell_id": config["cell_id"],
                    "actor": config["actor"], "entrypoint": "runner.py", "files": inline,
                    "recording_description": recording,
                    "measurement_plan": {"entrypoint": "finalize.py", "status": "source-bound CPU draft"},
                    "static_checks": ["one driving lane per direction", "nine exact pass plans",
                                      "four-camera 600-frame acquisition",
                                      "original electric-scooter survey classification"],
                    "termination_rules": ["600 original frames", "restore owned world"],
                    "mechanisms": ["Native car and surveyed scooter pose/body acquisition",
                                   "original lane and center marking readback"],
                    "status": "selected_cpu_draft_original_unobserved"}
        path = HERE / "selected-native-draft" / suffix / "construction.json"
        put(path, proposal)
        applicable = [(i, row) for i, row in enumerate(plan["requirement_dispositions"])
                      if row["status"] == "selected_required" and case in row["case_ids"]]
        if len(applicable) != 1:
            raise ValueError("Every selected case needs exactly one source requirement")
        index, disposition = applicable[0]
        contract = {"format": "worker-measurement-contract", "case_id": case,
                    "requirements": [{"disposition_index": index,
                                      "requirement": disposition["requirement"],
                                      "source": disposition["source"],
                                      "output_key": "scooter_pass", "method": "measure",
                                      "kind": "measured", "value_type": "object", "inputs": SOURCES}],
                    "negative": {"remove": ["pass-context.json"],
                                 "error_contains": "Missing required source: pass-context.json"}}
        put(HERE / (suffix + "-measurement-contract.json"), contract)
        entries.append({"case_id": case, "kind": "delivery",
                        "construction": str(path.relative_to(HERE)), "construction_sha256": sha(path),
                        "measurement_contract": suffix + "-measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "fixture_recipe": "work/" + AID + "/diagnostic/" + suffix + "/fixture-recipe.json",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "none", "reason":
                                           "No distinct local fallback removes the original scooter survey and physical readback requirements; these remain delivery gates"},
                        "candidates": [], "delivery_readiness": "incomplete"})
        proposal_cases["cases"].append({"case_id": case, "target_law_id": config["law_id"],
            "target_type": "controlled_attempt", "rationale": planned["physical_target"],
            "variable_assignments": {"comparison_variable": planned["comparison_variable"],
                                     "case_suffix": suffix},
            "unresolved_judgment_calls": planned.get("unresolved_judgment_calls", plan["unresolved_judgment_calls"]),
            "recording_description": recording})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(ROOT / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "selected_native_offline_draft", "delivery_ready": False,
                "cases": entries}
    put(HERE / "selected-native-draft-manifest.json", manifest)
    put(HERE / "proposals" / "cases.json", proposal_cases)
    return {"case_count": len(entries), "manifest_sha256": sha(HERE / "selected-native-draft-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
