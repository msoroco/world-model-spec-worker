"""Export the selected railroad primary as the assignment CPU entrypoint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    reference = next(case for case in manifest["cases"]
                     if case["case_id"].endswith("__rail_reference"))
    selected_path = HERE / reference["construction"]
    if sha(selected_path) != reference["construction_sha256"]:
        raise ValueError("Selected railroad primary changed")
    selected = json.loads(selected_path.read_text())
    files = {entry["path"]: entry["content"] for entry in selected["files"]}
    for name, content in files.items():
        if name == "config.json":
            continue
        target = HERE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    config = json.loads(files["config.json"])
    config["supported_case_ids"] = [case["case_id"] for case in manifest["cases"]]
    config["status"] = "assignment_cpu_entrypoint_physical_unverified"
    camera_specs = (
        ("overview", 90, "fixed world mount above rail and highway approach"),
        ("approach", 95, "fixed world mount facing the driver approach"),
        ("reference_corner", 90, "fixed world mount showing the crossing boundary"),
        ("driver_reference", 90, "ego-relative driver eye mount facing travel"),
    )
    for camera, (name, fov, pose) in zip(config["cameras"], camera_specs, strict=True):
        if camera["name"] != name:
            raise ValueError("Four source camera roles changed")
        camera["fov_deg"] = fov
        camera["pose_strategy"] = pose
    write(HERE / "config.json", config)
    construction = {key: value for key, value in selected.items() if key != "files"}
    construction["status"] = "assignment_cpu_entrypoint_physical_unverified"
    construction["selection_source"] = {
        "selected_primary": reference["construction"],
        "selected_primary_sha256": sha(selected_path),
        "execution_manifest_sha256": sha(MANIFEST),
    }
    construction["files"] = [
        {"path": name, "content": (HERE / name).read_text()}
        for name in files
    ]
    write(HERE / "construction.json", construction)
    return {"selected_primary_sha256": sha(selected_path),
            "root_construction_sha256": sha(HERE / "construction.json"),
            "supported_case_ids": config["supported_case_ids"],
            "source_files": len(construction["files"])}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
