"""Prepare four same-cell structural alternatives as CPU construction requests."""

import hashlib
import json
from pathlib import Path

from structure_variant import request, validate


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
METHODS = {
    "st.elevated_structure": "Original Native drivable deck, support bounds and four-view review",
    "drv.approaching": "Original Native speed and complete footprint before structure start",
    "rel.centre_distance": "Observed body front distance to structure start in metres",
    "st.sight_distance": "Original incoming-lane sight ray with source camera pixels",
    "drv.sight_distance_adequate": "Independent view judgment required; no ray cutoff",
    "st.centre_line": "Authored centerline and original opposed-lane map readback",
    "rel.occupies": "Original four-corner vehicle footprint relative to centerline",
    "st.one_way_roadway": "Original opposed-lane direction readback",
}
SOURCE_FILES = ("assignment-source.json", "road.xodr", "runner.py",
                "structure_capture.py", "finalize.py", "measure_structure.py",
                "measure_tunnel.py", "sight_proxy.py", "structure_variant.py",
                "structure_setup.py", "tunnel_scene.py")


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()


def build(kind, side, candidate="primary"):
    request_value = request(kind, side)
    validate(request_value)
    case_id = ASSIGNMENT + "__" + kind + "_" + side
    description = {"channels": [{"name": name, "unit": "structured",
        "sampling_rate_hz": 20, "method": method,
        "time_window": "all original 600 Native frames / 30 seconds",
        "reference_frame": "original Native road, actor and camera frame",
        "uncertainty": "50 ms sampling; physical and legal interpretation pending"}
        for name, method in METHODS.items()],
        "context_inputs": [{"name": "structure_source_context", "unit": "structured",
            "method": "Source-hashed original deck, support, direction and sight readback"}],
        "limitations": ["Authored raised road and support request need original Native physical review",
                        "No virtual sight-ray cutoff decides legal obstruction"]}
    source = {"assignment-source.json": (REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text(),
              "road.xodr": request_value["road_opendrive"],
              "runner.py": (HERE / "structure_runner.py").read_text(),
              "structure_capture.py": (HERE / "structure_capture.py").read_text(),
              "finalize.py": (HERE / "finalize_structure.py").read_text()}
    for name in SOURCE_FILES:
        if name in source:
            continue
        source[name] = (HERE / name).read_text()
    source["tests/test_structure_bundle.py"] = (HERE / "test_structure_bundle.py").read_text()
    config = {"format": "c313130-structure-selected-v1", "assignment_id": ASSIGNMENT,
        "case_id": case_id, "selected_case_id": case_id,
        "supported_case_ids": [case_id],
        "candidate_id": candidate, "law_id": "NRS-484B-213-2c",
        "cell_id": "C313130", "actor": "motor_vehicle_driver",
        "structure_kind": kind, "requested_lateral_target": side,
        "assignment_sha256": sha(source["assignment-source.json"]),
        "road_sha256": sha(source["road.xodr"]),
        "rate_hz": 20, "duration_frames": 600, "duration_s": 30,
        "required_atoms": ["kin.position", "kin.heading", "rel.occupies"],
        "source_packets": [], "mandatory_channels": list(METHODS),
        "native_execution_integrated": True, "original_native_observed": False,
        "physical_verified": False, "legal_verdict": None,
        "vehicle_blueprint": "vehicle.carlamotors.carlacola",
        "support_blueprint": "static.prop.constructionpillar",
        "tunnel_blueprint": "static.prop.tunnel",
        "occluder_blueprint": "static.prop.hedge",
        "controller_gain": 1.5 if candidate == "primary" else 2.0,
        "requested_left_side": side == "left",
        "cameras": [{"name": name, "fps": 20, "width": width,
            "height": height, "fov_deg": 85,
            "pose_strategy": "ego" if name == "driver_reference" else "world"}
            for name, width, height in CAMERAS],
        "recording_description": description,
        "case": {"case_id": case_id, "recording_description": description}}
    source["config.json"] = encode(config)
    construction = {"format": "worker-inline-construction", "case_id": case_id,
        "cell_id": "C313130", "law_id": "NRS-484B-213-2c",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": [{"path": name, "content": content} for name, content in source.items()],
        "measurement_plan": {"method": "Source-bound original structure, direction, body, sight and camera joins",
            "status": "cpu_prepared_original_native_unobserved"},
        "recording_description": description,
        "static_checks": ["exact assignment/road hashes", "original raised-deck readback",
                          "installed structural support bounds", "four-camera 20 Hz profile",
                          "600-frame source join"],
        "termination_rules": ["retain all 600 original frames", "retain failed attempt and restore world"],
        "mechanisms": ["authored fixed-cell opposed-lane raised OpenDRIVE",
                       "Native support and sight-occluder prop requests",
                       "source-bound lateral controller", "four synchronized lossless cameras"],
        "status": "selected_cpu_construction"}
    path = HERE / ("structure-construction-" + kind + "_" + side + "-" + candidate + ".json")
    path.write_text(encode(construction))
    return {"case_id": case_id, "candidate_id": candidate, "construction": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    built = [build(kind, side, candidate) for kind in ("bridge", "viaduct")
             for side in ("right", "left") for candidate in ("primary", "fallback1")]
    cases = []
    for kind in ("bridge", "viaduct"):
        for side in ("right", "left"):
            primary = next(row for row in built if row["case_id"].endswith(
                "__" + kind + "_" + side) and row["candidate_id"] == "primary")
            fallback = next(row for row in built if row["case_id"] == primary["case_id"]
                            and row["candidate_id"] == "fallback1")
            cases.append({"case_id": primary["case_id"], "kind": "delivery",
                "id": "primary", "construction": primary["construction"],
                "construction_sha256": primary["sha256"],
                "fixture_recipe": f"work/{ASSIGNMENT}/structure-recipe-{kind}_{side}.json",
                "measurement_contract": "structure-measurement-contract.json",
                "measurement_procedure": {"entrypoint": "finalize.py",
                    "output_schema": "worker-structure-selected-measurement"},
                "candidate_risk": {"status": "physical",
                    "reason": "Native structural support asset, physical identity and approach require original review"},
                "candidates": [{"id": "fallback1", "construction": fallback["construction"],
                    "construction_sha256": fallback["sha256"],
                    "trigger": {"source": "structure-rows.jsonl", "metric":
                        "full-body lateral discrepancy at 100-foot zone entry",
                        "failure_condition": "body remains over 1 m from requested lane center"},
                    "changed_knobs": ["controller_gain: 1.5 to 2.0"]}]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "status": "diagnostic_structure_probe", "cases": cases}
    (HERE / "structure-probe-manifest.json").write_text(encode(manifest))
    print(encode(built))
