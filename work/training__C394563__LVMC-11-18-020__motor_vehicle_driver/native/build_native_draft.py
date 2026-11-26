"""Build two exact source-bound Native draft bundles for offline checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from cameras import camera_plan


HERE = Path(__file__).resolve().parent
SOURCES = ("runner.py", "geometry.py", "cameras.py", "saved_source.py",
           "finalize.py", "test_saved_source.py", "test_native_survey.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    entries = []
    for suffix in ("a", "b"):
        old = json.loads((HERE / f"condition_{suffix}-construction.json").read_text())
        config = json.loads(next(item["content"] for item in old["files"]
                                 if item["path"] == "config.json"))
        config["required_atoms"] = []
        config["supported_case_ids"] = [
            json.loads((HERE / f"condition_{name}-construction.json").read_text())["case_id"]
            for name in ("a", "b")]
        config["recording_description"] = old["recording_description"]
        config["recording_description"]["context_inputs"] = []
        by_name = {item["name"]: item for item in camera_plan()}
        for camera in config["cameras"]:
            plan = by_name[camera["name"]]
            camera["fov_deg"] = plan["fov_deg"]
            camera["pose_strategy"] = plan["attachment"] + " fixed pose " + str(plan["xyz_m"])
        for channel in config["recording_description"]["channels"]:
            channel["unit"] = "source state"
            channel["reference_frame"] = "original Native frame and surveyed road geometry"
            channel["uncertainty"] = "50 ms event bracket; sign pixels and intent await review"
        config["physical_completion"] = {
            "criterion": "intersection_clearance", "motion_source": "body_history.jsonl",
            "body_key": "body_vertices_m", "context_sources": ["road_geometry.json"],
            "intersection_polygon_xy_m": [[0, -3.5], [3.6576, -3.5],
                                           [3.6576, 3.5], [0, 3.5]],
            "exit_axis": 0, "exit_sign": 1, "minimum_progress_m": 5.0,
            "engineering_tolerances_not_legal": True}
        config["source_observation_contract"] = "native school-crossing geometry, person and frame join"
        config["case"] = {"case_id": old["case_id"],
                          "recording_description": config["recording_description"]}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        for source in SOURCES:
            destination = "tests/" + source if source.startswith("test_") else source
            files.append({"path": destination, "content": (HERE / source).read_text()})
        construction = {"format": "worker-inline-construction",
                        "case_id": old["case_id"], "cell_id": "C394563",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": files, "recording_description": config["recording_description"],
                        "measurement_plan": [
                            {"method": "measure_marking_context", "source": "road_geometry.json"},
                            {"method": "measure_signed_entry", "source": "native_samples.jsonl"},
                            {"method": "measure_reviewed_scope", "source": "video_frames.jsonl"}],
                        "static_checks": ["yellow 3.6576 m marked crossing",
                                          "School-Xing sign >=30.48 m in advance",
                                          "two-direction original Native road readback"],
                        "termination_rules": ["600 original frames at 20 Hz",
                                              "close all camera encoders",
                                              "verify world restoration before sealing"],
                        "mechanisms": ["source-joined front-footprint entry",
                                       "approach-side person occupation at entry",
                                       "four original camera streams and explicit legal review"],
                        "status": "source_bound_native_draft",
                        "physical_acceptance_claimed": False}
        path = HERE / f"condition_{suffix}-native-construction.json"
        path.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": old["case_id"], "construction": path.name,
                        "construction_sha256": sha(path)})
    manifest = {"format": "draft-execution-manifest", "cases": entries}
    (HERE / "native-draft-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
