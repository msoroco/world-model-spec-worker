"""Build two exact source-bound Native draft bundles for offline checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
        config["recording_description"] = old["recording_description"]
        config["recording_description"]["context_inputs"] = []
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
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        for source in SOURCES:
            destination = "tests/" + source if source.startswith("test_") else source
            files.append({"path": destination, "content": (HERE / source).read_text()})
        construction = {"format": "worker-inline-construction",
                        "case_id": old["case_id"], "cell_id": "C394563",
                        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                        "files": files, "recording_description": config["recording_description"],
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
