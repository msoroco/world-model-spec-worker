"""Build eleven distinct source-gated exact construction drafts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "native"
ASSIGNMENT = ROOT.name
CAMERAS = (
    ("overview", 1920, 1080, [-7, 0, 5], [-20, 0, 0]),
    ("approach", 1280, 720, [3, 0, 2], [-4, 0, 0]),
    ("reference_corner", 1280, 720, [-3, 3, 2], [-5, -35, 0]),
    ("driver_reference", 1280, 720, [-7, 0, 2], [0, 180, 0]),
)
CHANNELS = ("drv.standing_or_parked", "st.shoulder", "rel.occupies",
            "drv.civil_night", "env.visibility", "sig.position_lamp",
            "sig.headlamp", "rel.bearing", "st.lane", "st.roadway")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shape(case):
    suffix = case["case_id"].split("__")[-1]
    if suffix == "witness_1":
        return "display", "none", None
    if suffix == "witness_2":
        return "omit", "none", None
    if suffix.startswith("numeric_"):
        _, number, index = suffix.split("_")
        number, index = int(number), int(index)
        names = {1: "ambient_reveal", 2: "front_white_or_amber", 3: "rear_red"}
        values = {1: (990, 1000, 1010), 2: (495, 500, 505),
                  3: (495, 500, 505)}
        return "display", names[number], values[number][index]
    raise ValueError("Unknown selected shape: " + suffix)


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    runner = (HERE / "selected_runner.py").read_text()
    tests = (HERE / "selected_offline_test.py").read_text()
    finalizer = (HERE / "finalize.py").read_text()
    saved = (HERE / "saved_shoulder.py").read_text()
    measure = (HERE / "shoulder_lamp_measure.py").read_text()
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20,
        "method": "Joined original Native survey, actor state, lamp bits and camera frame",
        "time_window": "all 600 frames / 30 seconds",
        "reference_frame": "original Native frame and elapsed time",
        "uncertainty": "optical distance and actual pixels need independent review"}
        for name in CHANNELS],
        "context_inputs": [{"name": "shoulder_lighting_survey", "unit": "structured",
                            "method": "independent original map, clock and optical protocol survey"}],
        "limitations": ["Commanded lamp bits do not prove colored emitted light",
                        "CARLA pixels do not establish calibrated 500-foot equipment visibility",
                        "Requested numeric target is not a measured result"]}
    selected = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        lamp, kind, distance = shape(case)
        disposition_index = {"none": 0, "ambient_reveal": 1,
                             "front_white_or_amber": 2, "rear_red": 3}[kind]
        output_key = {"none": "shoulder_lamp_display",
                      "ambient_reveal": "ambient_reveal_ft",
                      "front_white_or_amber": "front_visibility_ft",
                      "rear_red": "rear_visibility_ft"}[kind]
        cameras = [{"name": name, "width": width, "height": height,
                    "fps": 20, "fov_deg": 95, "location_xyz_m": xyz,
                    "rotation_pyr_deg": rotation}
                   for name, width, height, xyz, rotation in CAMERAS]
        config = {"case_id": case_id, "selected_case_id": case_id,
                  "law_id": "NRS-484D-165-3", "cell_id": "C183085",
                  "actor": "motor_vehicle_driver",
                  "frozen_cell": {"layout": "paved_shoulder",
                                  "maneuver": "stop_stand", "control": "other_vehicle"},
                  "status": "selected_cpu_construction_unverified",
                  "rate_hz": 20, "duration_s": 30, "frames": 600,
                  "vehicle_blueprint": "vehicle.tesla.model3",
                  "lamp_command": lamp, "optical_target_kind": kind,
                  "target_distance_ft": distance,
                  "required_atoms": [], "source_packets": [],
                  "cameras": cameras, "physical_completion": {}, "legal_verdict": None,
                  "recording_description": description,
                  "case": {"case_id": case_id, "recording_description": description}}
        construction = {"format": "worker-inline-construction", "case_id": case_id,
                        "law_id": "NRS-484D-165-3", "cell_id": "C183085",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": [{"path": "runner.py", "content": runner},
                                  {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                                  {"path": "tests/test_offline.py", "content": tests},
                                  {"path": "finalize.py", "content": finalizer},
                                  {"path": "saved_shoulder.py", "content": saved},
                                  {"path": "shoulder_lamp_measure.py", "content": measure}],
                        "recording_description": description,
                        "status": "selected_cpu_construction_unverified"}
        path = HERE / ("selected-" + case_id.split("__")[-1] + "-construction.json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": disposition_index,
                                      "requirement": "NRS-484D-165-3",
                                      "source": "NRS 484D.165(3); with 484D.165(1)",
                                      "output_key": output_key,
                                      "method": "measure_selected_requirement",
                                      "value_type": "object", "kind": "measured",
                                      "inputs": ["shoulder-lamp-trace.jsonl",
                                                 "video_frames.jsonl",
                                                 "shoulder_lighting_survey.json",
                                                 "optical_measurements.json"]}],
                    "negative": {"remove": ["optical_measurements.json"],
                                 "error_contains":
                                     "Missing required source: optical_measurements.json"}}
        contract_path = HERE / ("selected-" + case_id.split("__")[-1] +
                                "-measurement-contract.json")
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        selected.append({"case_id": case_id, "kind": "delivery", "id": "primary",
                         "construction": str(path.relative_to(ROOT)),
                         "construction_sha256": sha(path), "candidates": [],
                         "measurement_contract": str(contract_path.relative_to(ROOT)),
                         "measurement_procedure": {"entrypoint": "finalize.py",
                                                   "status": "saved_source_diagnostic"},
                         "fixture_recipe": "work/" + ASSIGNMENT + "/native/selected-" +
                                           case_id.split("__")[-1] + "-fixture-recipe.json",
                         "candidate_risk": {"status": "physical",
                            "reason": "Original shoulder, clock, optics and four views need Native review"}})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256":
                    "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
                "status": "selected_offline_only", "cases": selected,
                "original_native_observed": False, "delivery_ready": False}
    path = ROOT / "selected-shoulder-draft-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(selected), "manifest_sha256": sha(path),
                      "construction_sha256": {c["case_id"].split("__")[-1]:
                          c["construction_sha256"] for c in selected}}, sort_keys=True))


if __name__ == "__main__":
    main()
