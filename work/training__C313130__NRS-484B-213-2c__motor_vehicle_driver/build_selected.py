"""Bind exact tunnel cases to source-owned Native construction requests."""

import hashlib
import json
from pathlib import Path

from tunnel_scene import open_drive, scene_request, validate_request


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
CHANNELS = {
    "st.elevated_structure": "Native tunnel prop bounds, authored portal and original four-view review",
    "drv.approaching": "Original Native ego speed and complete footprint before tunnel portal",
    "rel.centre_distance": "Observed body front distance to portal in metres, with exact 30.48 m comparison",
    "st.sight_distance": "Original Native incoming-lane sight ray and source camera pixels; unknown if unavailable",
    "drv.sight_distance_adequate": "No automatic judgment from ray proxy; independent view review needed",
    "st.centre_line": "Authored centerline and original opposed-lane Native map readback",
    "rel.occupies": "Original Native four-corner vehicle footprint relative to reviewed highway center",
    "st.one_way_roadway": "Original Native opposed-lane direction readback",
}


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def build(suffix):
    case_id = ASSIGNMENT + "__" + suffix
    request = scene_request(suffix)
    validate_request(request)
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "method": method,
        "time_window": "all original 600 Native frames / 30 seconds",
        "reference_frame": "original Native road, actor and camera frame",
        "uncertainty": "50 ms sampling; physical and legal interpretation pending"}
        for name, method in CHANNELS.items()],
        "context_inputs": [{"name": "tunnel_source_context", "unit": "structured",
            "method": "Source-hashed original map, portal bounds and road direction readback"}],
        "limitations": ["A tunnel prop and virtual ray do not establish a real public highway or legal obstruction",
                        "Original pixels, portal identity, ray validity and body trajectory require review"]}
    files = {"assignment-source.json": (REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text(),
        "road.xodr": open_drive(), "runner.py": (HERE / "runner.py").read_text(),
        "native_capture.py": (HERE / "native_capture.py").read_text(),
        "finalize.py": (HERE / "finalize.py").read_text(),
        "measure_tunnel.py": (HERE / "measure_tunnel.py").read_text(),
        "tunnel_scene.py": (HERE / "tunnel_scene.py").read_text(),
        "tests/test_selected.py": (HERE / "test_selected.py").read_text()}
    config = {"format": "c313130-tunnel-selected-v1", "case_id": case_id,
        "selected_case_id": case_id, "supported_case_ids": [case_id],
        "candidate_id": "primary", "law_id": "NRS-484B-213-2c",
        "cell_id": "C313130", "actor": "motor_vehicle_driver",
        "assignment_sha256": sha(files["assignment-source.json"]),
        "road_sha256": sha(files["road.xodr"]),
        "rate_hz": 20, "duration_frames": 600, "duration_s": 30,
        "required_atoms": ["kin.position", "kin.heading", "rel.occupies"],
        "source_packets": [], "mandatory_channels": list(CHANNELS),
        "native_execution_integrated": True, "original_native_observed": False,
        "physical_verified": False, "legal_verdict": None,
        "vehicle_blueprint": request["vehicle"]["blueprint"],
        "tunnel_blueprint": request["tunnel"]["blueprint"],
        "occluder_blueprint": request["occluder"]["blueprint"],
        "requested_left_side": suffix == "probe_2",
        "cameras": [{"name": name, "fps": 20, "width": width,
            "height": height, "fov_deg": 85, "pose_strategy":
            "ego" if name == "driver_reference" else "world"}
            for name, width, height in CAMERAS],
        "recording_description": description,
        "case": {"case_id": case_id, "recording_description": description}}
    files["config.json"] = encode(config)
    construction = {"format": "worker-inline-construction", "case_id": case_id,
        "cell_id": "C313130", "law_id": "NRS-484B-213-2c",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": [{"path": name, "content": content} for name, content in files.items()],
        "measurement_plan": {"method": "Source-bound original tunnel portal, direction, body, sight and camera joins",
                             "status": "cpu_prepared_original_native_unobserved"},
        "recording_description": description,
        "static_checks": ["exact assignment/road hashes", "opposed driving lane readback",
                          "four camera 20 Hz profile", "600-frame source join"],
        "termination_rules": ["retain all 600 original frames", "retain failed attempt and restore world"],
        "mechanisms": ["authored OpenDRIVE opposed lanes", "Native tunnel and occluder props",
                       "source-bound lateral controller", "four synchronized lossless cameras"],
        "status": "selected_cpu_construction"}
    name = "selected-construction-" + suffix + ".json"
    (HERE / name).write_text(encode(construction))
    return {"case_id": case_id, "kind": "delivery", "id": "primary",
        "construction": name, "construction_sha256":
        hashlib.sha256((HERE / name).read_bytes()).hexdigest(),
        "fixture_recipe": f"work/{ASSIGNMENT}/selected-recipe-{suffix}.json",
        "measurement_contract": "selected-measurement-contract.json",
        "measurement_procedure": {"entrypoint": "finalize.py",
                                  "output_schema": "worker-tunnel-selected-measurement"},
        "candidate_risk": {"status": "physical", "reason":
            "Tunnel prop, occlusion and lateral tracking require original Native review"},
        "candidates": []}


def main():
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "status": "diagnostic_selected_probe",
        "cases": [build(suffix) for suffix in ("probe_1", "probe_2")]}
    path = HERE / "selected-probe-manifest.json"
    path.write_text(encode(manifest))
    description = json.loads((HERE / "selected-construction-probe_1.json").read_text())["recording_description"]
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Neutral unselected comparison context",
        "variable_assignments": {"requested_lateral_target": {"kind": "controller",
            "value": "right", "unit": "categorical"}},
        "unresolved_judgment_calls": [], "recording_description": description}
    cases = [baseline]
    for suffix, target in (("probe_1", "right"), ("probe_2", "left")):
        cases.append({"case_id": ASSIGNMENT + "__" + suffix,
            "target_law_id": "NRS-484B-213-2c", "target_type": "controlled_attempt",
            "rationale": "Measure full-body lateral position during source-identified tunnel approach",
            "variable_assignments": {"requested_lateral_target": {"kind": "controller",
                "value": target, "unit": "categorical"},
                "observed_left_occupancy": {"kind": "subject_behavior",
                    "value": None, "unit": "per frame"},
                "view_obstructed": {"kind": "world_setup",
                    "value": None, "unit": "original source review"}},
            "unresolved_judgment_calls": ["legal meaning of obstructed view"],
            "paired_probe_id": ASSIGNMENT + "__comparison",
            "deliberate_differences": ["requested_lateral_target"],
            "recording_description": description})
    proposals = {"cell_id": "C313130", "actor": "motor_vehicle_driver",
        "status": "draft", "cases": cases, "sweep_specs": []}
    proposal = HERE / "proposals/cases.json"
    proposal.parent.mkdir(exist_ok=True)
    proposal.write_text(encode(proposals))
    print(json.dumps({"manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "case_ids": [case["case_id"] for case in manifest["cases"]]}))


if __name__ == "__main__":
    main()
