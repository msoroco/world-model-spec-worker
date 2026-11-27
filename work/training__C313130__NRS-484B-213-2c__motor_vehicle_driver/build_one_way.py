"""Build exact one-way tunnel constructions for offline CPU preparation."""

import hashlib
import json
from pathlib import Path

from build_selected import CAMERAS, CHANNELS, encode, sha
from one_way_variant import TARGETS, road_xml, request


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name


def build(case, candidate_id):
    case_id = ASSIGNMENT + "__" + case
    scene = request(case)
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "method": method,
        "time_window": "all original 600 Native frames / 30 seconds",
        "reference_frame": "original Native road, actor and camera frame",
        "uncertainty": "50 ms sampling; physical and legal interpretation pending"}
        for name, method in CHANNELS.items()],
        "context_inputs": [{"name": "tunnel_source_context", "unit": "structured",
            "method": "Source-hashed original map, portal bounds and one-way direction readback"}],
        "limitations": ["Authored one-way road does not establish a legal one-way public highway",
                        "Tunnel identity and obstruction require original Native pixels and review"]}
    files = {
        "assignment-source.json": (REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text(),
        "road.xodr": road_xml(),
        "runner.py": (HERE / "one_way_runner.py").read_text(),
        "one_way_capture.py": (HERE / "one_way_capture.py").read_text(),
        "finalize.py": (HERE / "finalize.py").read_text(),
        "measure_tunnel.py": (HERE / "measure_tunnel.py").read_text(),
        "tests/test_one_way.py": (HERE / "test_one_way.py").read_text(),
    }
    gain = 1.5 if candidate_id == "primary" else 2.0
    config = {"format": "c313130-one-way-tunnel-selected-v1", "case_id": case_id,
        "selected_case_id": case_id, "supported_case_ids": [case_id],
        "candidate_id": candidate_id, "law_id": "NRS-484B-213-2c",
        "cell_id": "C313130", "actor": "motor_vehicle_driver",
        "assignment_sha256": sha(files["assignment-source.json"]),
        "road_sha256": sha(files["road.xodr"]),
        "rate_hz": 20, "duration_frames": 600, "duration_s": 30,
        "required_atoms": ["kin.position", "kin.heading", "rel.occupies"],
        "source_packets": [], "mandatory_channels": list(CHANNELS),
        "native_execution_integrated": True, "original_native_observed": False,
        "physical_verified": False, "legal_verdict": None,
        "vehicle_blueprint": "vehicle.carlamotors.carlacola",
        "tunnel_blueprint": scene["tunnel_blueprint"],
        "occluder_blueprint": scene["occluder_blueprint"],
        "controller_gain": gain,
        "requested_left_side": case == "one_way_left",
        "highway_centre_y_m": scene["highway_centre_y_m"],
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
        "measurement_plan": {"method":
            "Original one-way road direction, tunnel portal, body, sight and four-camera join",
            "status": "cpu_prepared_original_native_unobserved"},
        "recording_description": description,
        "static_checks": ["exact assignment/road hashes", "two eastbound driving lanes",
                          "four camera 20 Hz profile", "600-frame source join"],
        "termination_rules": ["retain all 600 original frames",
                              "retain failed attempt and restore world"],
        "mechanisms": ["authored one-way OpenDRIVE lanes -1 and -2",
                       "Native tunnel and occluder props", "source-bound lateral controller",
                       "four synchronized lossless cameras"],
        "status": "selected_cpu_construction"}
    name = "one-way-construction-" + case + "-" + candidate_id + ".json"
    (HERE / name).write_text(encode(construction))
    return name, hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def main():
    entries = []
    for case in TARGETS:
        primary, primary_sha = build(case, "primary")
        fallback, fallback_sha = build(case, "fallback1")
        entries.append({"case_id": ASSIGNMENT + "__" + case,
            "kind": "delivery", "id": "primary",
            "construction": primary, "construction_sha256": primary_sha,
            "measurement_contract": "selected-measurement-contract.json",
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "worker-tunnel-selected-measurement"},
            "candidate_risk": {"status": "physical", "reason":
                "Native one-way road, tunnel prop, occlusion and lateral tracking need review"},
            "candidates": [{"id": "fallback1", "construction": fallback,
                "construction_sha256": fallback_sha,
                "trigger": {"source": "tunnel-rows.jsonl", "metric":
                    "full-body lateral discrepancy at 100-foot zone entry",
                    "failure_condition": "body remains over 1 m from requested lane center"},
                "changed_knobs": ["controller_gain: 1.5 to 2.0"]}]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": hashlib.sha256(
            (REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "status": "diagnostic_selected_probe", "cases": entries}
    path = HERE / "one-way-probe-manifest.json"
    path.write_text(encode(manifest))
    print(json.dumps({"case_ids": [entry["case_id"] for entry in entries],
                      "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
