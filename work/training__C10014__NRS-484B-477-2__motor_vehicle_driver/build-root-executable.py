"""Materialize the assignment-level CPU executable from the selected primary.

The selected candidate and its proof receipts are immutable inputs to this step.
This package is a dispatch/default entrypoint; the execution manifest continues
to select the exact case and fallback construction for delivery.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SELECTED = ROOT / "selected-candidates/reference/primary/construction.json"
MANIFEST = ROOT / "execution-manifest.json"
SOURCE_FILES = (
    "runner.py", "geometry.py", "controller.py", "engineering.py",
    "cameras.py", "measure_entrance.py", "finalize.py",
)
TEST = "tests/test_root_selected.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build() -> dict:
    selected = json.loads(SELECTED.read_text())
    manifest = json.loads(MANIFEST.read_text())
    reference = next(c for c in manifest["cases"] if c["case_id"].endswith("__reference"))
    if reference["construction_sha256"] != sha(SELECTED):
        raise ValueError("Selected primary changed after its proof binding")
    source = {entry["path"]: entry["content"] for entry in selected["files"]}
    for name in SOURCE_FILES:
        (ROOT / name).write_text(source[name])

    config = json.loads(source["config.json"])
    config["supported_case_ids"] = [c["case_id"] for c in manifest["cases"]]
    config["status"] = "assignment_cpu_entrypoint_physical_unverified"
    camera_specs = (
        ("overview", 90, "world mount at (-8,-12,9) m"),
        ("approach", 95, "world mount at (-18,-2,5) m"),
        ("reference_corner", 90, "world mount at (0,-13,6) m"),
        ("driver_reference", 90, "ego mount at (1,0,2.2) m"),
    )
    for camera, (name, fov, pose) in zip(config["cameras"], camera_specs, strict=True):
        if camera["name"] != name:
            raise ValueError("Selected primary camera order changed")
        camera["fov_deg"] = fov
        camera["pose_strategy"] = pose
    write_json(ROOT / "config.json", config)

    construction = {key: value for key, value in selected.items() if key != "files"}
    construction["status"] = "assignment_cpu_entrypoint_physical_unverified"
    construction["selection_source"] = {
        "selected_primary": SELECTED.relative_to(ROOT).as_posix(),
        "selected_primary_sha256": sha(SELECTED),
        "execution_manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "execution_manifest_sha256": sha(MANIFEST),
    }
    construction["files"] = [
        {"path": name, "content": (ROOT / name).read_text()}
        for name in (*SOURCE_FILES, "config.json", TEST)
    ]
    write_json(ROOT / "construction.json", construction)

    offline_manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": manifest["assignment_id"],
        "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
        "cases": [
            {
                **{key: value for key, value in reference.items()
                   if key not in ("candidates", "offline", "compatibility", "negative")},
                "construction": "construction.json",
                "construction_sha256": sha(ROOT / "construction.json"),
                "candidates": [],
            }
        ],
    }
    write_json(ROOT / "root-offline-manifest.json", offline_manifest)
    return {
        "selected_primary_sha256": sha(SELECTED),
        "root_construction_sha256": sha(ROOT / "construction.json"),
        "root_offline_manifest_sha256": sha(ROOT / "root-offline-manifest.json"),
        "source_files": list(SOURCE_FILES),
        "supported_case_ids": config["supported_case_ids"],
        "status": "CPU materialized; original physical run unverified",
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
