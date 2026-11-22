"""Build three source-bound exact pedestrian offline construction bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import CAMERA_SPECS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("roadway_walk", "sidewalk_walk", "shoulder_walk")
SOURCES = ("runner.py", "native_capture.py", "native_driver.py",
           "corridor_construction.py", "corridor_map.py", "saved_measurement.py",
           "delivery_audit.py", "comparison_audit.py", "analysis.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def file_entry(path, source):
    return {"path": path, "source": str(source.relative_to(REPO)),
            "content": source.read_text()}


def description():
    return {"channels": [
        {"name": "walker_body_xy_m", "unit": "m",
         "method": "eight world-space original CARLA walker body vertices at 20 Hz",
         "time_window": "all captured frames", "sampling_rate_hz": 20,
         "reference_frame": "authored OpenDRIVE world XY", "uncertainty": "CARLA bounding box readback"},
        {"name": "walker_route_progress", "unit": "m and s",
         "method": "original pose, body, velocity and frame timestamps",
         "time_window": "all captured frames", "sampling_rate_hz": 20,
         "reference_frame": "authored OpenDRIVE world XY", "uncertainty": "sampled frame interval"}],
        "context_inputs": [
         {"name": "sidewalk_roadway_shoulder_trail_context", "unit": "source and pixels",
          "method": "source-hashed authored OpenDRIVE plus four original camera views"}],
        "limitations": ["Authored corridor is an engineering candidate; sidewalk purpose and trail access require source review.",
                        "Requested pedestrian control and generated diagnostics do not prove realized walking or actual pixel visibility."]}


def config(scene):
    strategies = {"overview": "whole corridor and walker from above",
                  "approach": "route approach toward walking body",
                  "reference_corner": "sidewalk context toward walking body",
                  "driver_reference": "trail context toward walking body"}
    return {"law_id": "LVMC-11-30-090", "cell_id": "C143766",
            "actor": "pedestrian", "selected_case_id": scene["case_id"],
            "rate_hz": 20, "duration_s": 435/20,
            "required_atoms": [], "source_packets": [],
            "cameras": [{"name": name, "width": width, "height": height,
                         "fov_deg": 75, "pose_strategy": strategies[name]}
                        for name, (width, height) in CAMERA_SPECS.items()],
            "case": {"case_id": scene["case_id"],
                     "physical_target": scene["route_band"]+" walker body along corridor",
                     "recording_description": description()},
            "physical_completion": {"format": "worker-physical-completion-criteria",
                                    "criterion": "travel_progress",
                                    "motion_source": "walker-body-history.jsonl",
                                    "body_key": "body_xy_m",
                                    "minimum_progress_m": 20,
                                    "minimum_samples": 435,
                                    "direction_xy": [1, 0],
                                    "engineering_tolerances_not_legal": True}}


def build():
    entries = []
    for suffix in SUFFIXES:
        folder = HERE/"cases"/suffix
        scene_path = folder/"scene.json"
        scene = json.loads(scene_path.read_text())
        cfg_path = folder/"config.json"
        write(cfg_path, config(scene))
        files = [file_entry(name, HERE/name) for name in SOURCES]
        files += [file_entry("candidate-corridor.xodr", HERE/"candidate-corridor.xodr"),
                  file_entry("scene.json", scene_path),
                  file_entry("measurement-contract.json", folder/"measurement-contract.json"),
                  file_entry("config.json", cfg_path),
                  file_entry("tests/test_offline.py", HERE/"offline_test.py")]
        construction = {"law_id": "LVMC-11-30-090", "cell_id": "C143766",
                        "actor": "pedestrian", "case_id": scene["case_id"],
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": description(),
                        "measurement_plan": {"pedestrian_corridor_occupancy":
                            "Source-bound original whole-body roadway, sidewalk or shoulder occupancy; no legal verdict"},
                        "termination_rules": {"duration_s": 435/20,
                            "early_termination": "retain unsealed failed original attempt"},
                        "mechanisms": ["source-hashed five-band candidate OpenDRIVE",
                                       "Native walker control from original pose",
                                       "four original frame-joined cameras"],
                        "source_scene_sha256": sha(scene_path),
                        "source_map_sha256": scene["map_source_sha256"]}
        packet_path = folder/"construction.json"
        write(packet_path, construction)
        fallback = json.loads(json.dumps(construction))
        fallback["files"] = [
            file_entry("native_driver.py", HERE/"fallback_native_driver.py")
            if item["path"] == "native_driver.py" else item
            for item in fallback["files"]]
        fallback["mechanisms"] = construction["mechanisms"] + [
            "fallback walker request capped at 1.05 m/s while preserving the exact route"]
        fallback_path = folder/"fallback1-construction.json"
        write(fallback_path, fallback)
        entries.append({"case_id": scene["case_id"],
                        "construction": str(packet_path.relative_to(HERE)),
                        "construction_sha256": sha(packet_path),
                        "candidates": [{"id": "fallback1",
                            "construction": str(fallback_path.relative_to(HERE)),
                            "construction_sha256": sha(fallback_path),
                            "changed_knobs": ["walker requested speed 1.2 to 1.05 m/s"],
                            "trigger": {"source": "original walker-body-history.jsonl",
                                        "metric": "whole-body band occupancy or forward progress",
                                        "failure_condition": "primary original body leaves band or misses 20 m progress"}}]})
    draft = {"format": "c143766-draft-offline-manifest",
             "assignment_id": HERE.name, "cases": entries,
             "limitations": "Offline construction only; no delivery-ready claim or execution manifest."}
    write(HERE/"draft-offline-manifest.json", draft)
    return draft


if __name__ == "__main__":
    print(json.dumps({"cases": [entry["case_id"] for entry in build()["cases"]]}))
