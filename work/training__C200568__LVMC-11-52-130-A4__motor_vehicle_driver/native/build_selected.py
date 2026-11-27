"""Emit all fourteen exact case constructions from the source-hashed plan."""

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
CHANNELS = ("st.fire_hydrant", "rel.centre_distance", "st.parking_space",
            "dev.regulatory_sign", "drv.standing_or_parked", "kin.extent", "st.curb_zone")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shape(case):
    suffix = case["case_id"].split("__")[-1]
    if suffix == "witness_1":
        return "angle_permitted", 22, "none"
    if suffix == "witness_2":
        return "angle_permitted", 19.5, "none"
    if suffix.startswith("numeric_1_"):
        return "parallel_permitted", (14.5, 15, 15.5)[int(suffix[-1])], "none"
    if suffix.startswith("numeric_2_"):
        return "angle_permitted", (19.5, 20, 20.5)[int(suffix[-1])], "none"
    if suffix.startswith("exception_"):
        parts = suffix.split("_")
        context = ("traffic_conflict", "other_law", "officer_or_device")[int(parts[1]) - 1]
        return "angle_permitted", 19.5, context if parts[2] == "2" else "none"
    raise ValueError("Unknown selected shape: " + suffix)


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    runner = (HERE / "selected_runner.py").read_text()
    tests = (HERE / "selected_offline_test.py").read_text()
    finalizer = (HERE / "finalize.py").read_text()
    saved = (HERE / "saved_hydrant.py").read_text()
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20,
        "method": "Joined original Native pose, inventory, permission survey and camera frame",
        "time_window": "all 600 frames / 30 seconds",
        "reference_frame": "original Native frame and elapsed time",
        "uncertainty": "original survey and pixels need independent review"}
        for name in CHANNELS],
        "context_inputs": [{"name": "hydrant_parking_survey", "unit": "structured",
                            "method": "independent original premises, permission and hydrant survey"}],
        "limitations": ["Curb paint does not select the statutory distance",
                        "Exception declarations do not establish legal applicability",
                        "CPU fixtures do not prove original motion or physical completion"]}
    selected = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        regime, distance, exception = shape(case)
        cameras = [{"name": name, "width": width, "height": height,
                    "fps": 20, "fov_deg": 95, "location_xyz_m": xyz,
                    "rotation_pyr_deg": rotation}
                   for name, width, height, xyz, rotation in CAMERAS]
        config = {"case_id": case_id, "selected_case_id": case_id,
                  "law_id": "LVMC-11-52-130-A4", "cell_id": "C200568",
                  "actor": "motor_vehicle_driver",
                  "frozen_cell": {"layout": "public_access_premises",
                                  "maneuver": "park", "control": "fire_hydrant"},
                  "status": "selected_cpu_construction_unverified",
                  "rate_hz": 20, "duration_s": 30, "frames": 600,
                  "vehicle_blueprint": "vehicle.tesla.model3",
                  "parking_permission": regime,
                  "requested_clearance_ft": distance,
                  "exception_context": exception,
                  "exception_source_verified": False,
                  "required_atoms": list(CHANNELS),
                  "cameras": cameras, "physical_completion": {}, "legal_verdict": None,
                  "recording_description": description,
                  "case": {"case_id": case_id, "recording_description": description}}
        construction = {"format": "worker-inline-construction", "case_id": case_id,
                        "law_id": "LVMC-11-52-130-A4", "cell_id": "C200568",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": [{"path": "runner.py", "content": runner},
                                  {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                                  {"path": "tests/test_offline.py", "content": tests},
                                  {"path": "finalize.py", "content": finalizer},
                                  {"path": "saved_hydrant.py", "content": saved}],
                        "recording_description": description,
                        "status": "selected_cpu_construction_unverified"}
        path = HERE / ("selected-" + case_id.split("__")[-1] + "-construction.json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        selected.append({"case_id": case_id, "construction": str(path.relative_to(ROOT)),
                         "construction_sha256": sha(path), "candidates": [],
                         "candidate_risk": {"status": "physical",
                            "reason": "Original hydrant, permission, parking maneuver and four views need Native review."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "selected_offline_only",
                "cases": selected, "original_native_observed": False,
                "delivery_ready": False}
    path = ROOT / "selected-hydrant-draft-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(selected), "manifest_sha256": sha(path),
                      "construction_sha256": {c["case_id"].split("__")[-1]:
                          c["construction_sha256"] for c in selected}}, sort_keys=True))


if __name__ == "__main__":
    main()
