"""Materialize exact railway scene targets and portable source bundles."""
from __future__ import annotations

import json
from pathlib import Path

from rail_construction import TARGETS

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
MODULES = (
    "runner.py", "rail_native_runner.py", "rail_construction.py",
    "rail_exception_construction.py", "rail_exception_reader.py",
    "rail_route_reader.py", "rail_ray_reader.py", "rail_camera_adapter.py",
    "rail_native_capture.py", "rail_sight_measurement.py",
    "rail_saved_measurement.py", "rail_diagnostic_measurement.py",
    "rail_media_finalize.py", "rail_core_projection.py",
    "rail_postprocess.py", "analysis.py", "rail_comparison_audit.py",
    "tests/test_offline.py",
)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan["assignment_id"] != ASSIGNMENT or len(plan["cases"]) != len(TARGETS):
        raise ValueError("exact railway plan differs")
    for case in plan["cases"]:
        case_id = case["case_id"]
        key = case_id.removeprefix(ASSIGNMENT + "__")
        if (key not in TARGETS or case_id != ASSIGNMENT + "__" + key or
                case["engineering_target_traversal_mph"] != TARGETS[key][0] or
                (case["engineering_sight_setup"] == "obscured") is not TARGETS[key][1]):
            raise ValueError("railway case/target mismatch")
        target_exception = TARGETS[key][2]
        if case["exception_setup"] == "none":
            match = target_exception == "none"
        else:
            match = target_exception != "none"
        if not match:
            raise ValueError("railway exception target mismatch")
        scene = {
            "assignment_id": ASSIGNMENT, "case_id": case_id,
            "case_key": key, "cell_id": "C410753", "law_id": "LVMC-11-16-030",
            "actor": "motor_vehicle_driver", "target_mph": TARGETS[key][0],
            "obscured_sight_target": TARGETS[key][1],
            "exception_target": target_exception,
            "duration_frames": 900, "rate_hz": 20,
            "physical_completion_confirmed": False,
        }
        folder = HERE / "cases" / key
        write_json(folder / "scene.json", scene)
        config = {
            "assignment_id": ASSIGNMENT, "selected_case_id": case_id,
            "law_id": "LVMC-11-16-030", "cell_id": "C410753",
            "actor": "motor_vehicle_driver", "duration_s": 45,
            "rate_hz": 20, "required_atoms": [], "source_packets": [],
            "physical_completion": False, "case": case,
            "cameras": [
                {"name": name, "width": width, "height": height,
                 "fov_deg": 90,
                 "pose_strategy": "source-reviewed railway crossing operator pose"}
                for name, (width, height) in (
                    ("overview", (1920, 1080)), ("approach", (1280, 720)),
                    ("reference_corner", (1280, 720)),
                    ("driver_reference", (1280, 720)))]}
        write_json(folder / "config.json", config)
        files = [{"path": name, "source": "work/" + ASSIGNMENT + "/" + name,
                  "content": (HERE / name).read_text()} for name in MODULES]
        files.append({"path": "scene.json", "content":
                      (folder / "scene.json").read_text()})
        files.append({"path": "config.json", "content":
                      (folder / "config.json").read_text()})
        files.append({"path": "measurement-contract.json", "content":
                      (folder / "measurement-contract.json").read_text()})
        construction = {
            "assignment_id": ASSIGNMENT, "case_id": case_id,
            "law_id": "LVMC-11-16-030", "cell_id": "C410753",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
            "files": files,
            "mechanisms": [
                "source-reviewed Native road/rail crossing and route",
                "exact case speed, sight occluder and independent exception target",
                "source-sealed original 900-frame four-camera Native capture",
                "owner-released saved-only sight/exception analysis and FFV1 media"],
            "measurement_plan": {
                "traversal_speed": "Original ego body crossing occupancy and speed in mph",
                "sight_condition": "Original 100-foot approach and 400-foot bidirectional railway rays",
                "exceptions": "On-duty flagman and clearly visible installed nonwarning signal separately"},
            "recording_description": {
                "channels": [
                    {"name": "original_native_frame_history", "method":
                     "Sealed Native body, route, ray and exception readbacks",
                     "unit": "structured frame", "sampling_rate_hz": 20,
                     "time_window": "900 original frames at 20 Hz",
                     "reference_frame": "original Native world frame and crossing route",
                     "uncertainty": "20 Hz sample and reviewed map/body precision"},
                    {"name": "four_original_camera_streams", "method":
                     "Synchronized Native BGRA samples retained as PNG before FFV1",
                     "unit": "original camera frame", "sampling_rate_hz": 20,
                     "time_window": "900 original frames at 20 Hz",
                     "reference_frame": "four original Native camera views",
                     "uncertainty": "camera projection and pixel resolution"}],
                "context_inputs": [
                    {"name": "reviewed_railway_site", "unit": "source packet",
                     "method": "Source-hashed municipal road/rail map, route and jurisdiction review"},
                    {"name": "reviewed_exception_authority", "unit": "source packet",
                     "method": "Source-hashed flagman/signal installation and duty review"}],
                "limitations": [
                    "Physical sight, motion, image visibility and legal judgment remain for local review."]},
            "static_checks": [
                "exact case and frozen cell identity",
                "source-hashed road, route, railway rays, exceptions and occluder review",
                "contiguous original frame and four-camera joins"],
            "termination_rules": [
                "stop at 900 original 20 Hz Native frames",
                "abort on missing or changed original source/readback"],
        }
        write_json(folder / "construction.json", construction)
        if key == "obscured_14mph":
            write_json(HERE / "construction.json", construction)
            write_json(HERE / "scene.json", scene)
            write_json(HERE / "config.json", config)
    return len(plan["cases"])


if __name__ == "__main__":
    print(json.dumps({"selected_constructions": build()}))
