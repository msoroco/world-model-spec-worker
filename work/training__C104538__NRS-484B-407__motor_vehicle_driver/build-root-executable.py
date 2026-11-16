"""Materialize the assignment entrypoint from the tested selected primary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECTED = HERE / "selected-candidates/below_500_ft/primary/construction.json"
MANIFEST = HERE / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> dict:
    selected = json.loads(SELECTED.read_text())
    manifest = json.loads(MANIFEST.read_text())
    reference = next(case for case in manifest["cases"]
                     if case["case_id"].endswith("__below_500_ft"))
    if reference["construction_sha256"] != sha(SELECTED):
        raise ValueError("Selected primary changed")
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
        ("overview", 90, "fixed world mount 8 m above the curve/crest and U-turn envelope"),
        ("approach", 95, "fixed world mount 4 m before the driver approach position"),
        ("reference_corner", 90, "fixed world mount at the opposing driver sightline corner"),
        ("driver_reference", 90, "ego-relative mount at driver eye height facing travel"),
    )
    for camera, (name, fov, pose) in zip(config["cameras"], camera_specs, strict=True):
        if camera["name"] != name:
            raise ValueError("Four source camera roles changed")
        camera["fov_deg"] = fov
        camera["pose_strategy"] = pose
    write(HERE / "config.json", config)
    construction = {key: value for key, value in selected.items() if key != "files"}
    construction["status"] = "assignment_cpu_entrypoint_physical_unverified"
    construction["measurement_plan"] = {
        "method": "Original Native reversal point, curve/crest geometry and approaching-driver eye-to-body visibility from both directions; see measure_native.py, sightline.py and finalize.py",
        "status": "cpu_software_compatible_physical_unverified",
    }
    construction["static_checks"] = [
        "authored curve, crest and 450/500/550-foot obstruction geometry",
        "twenty Native construction and source-measurement unit tests",
        "twelve selected primary/fallback offline and saved-processing proofs",
        "independent two-direction source and controlled-comparison audits",
    ]
    construction["selection_source"] = {
        "selected_primary": SELECTED.relative_to(HERE).as_posix(),
        "selected_primary_sha256": sha(SELECTED),
        "execution_manifest_sha256": sha(MANIFEST),
    }
    construction["files"] = [
        {"path": name, "content": (HERE / name).read_text()}
        for name in (*[n for n in files if n != "config.json" ],
                     "config.json")
    ]
    write(HERE / "construction.json", construction)
    return {"selected_primary_sha256": sha(SELECTED),
            "root_construction_sha256": sha(HERE / "construction.json"),
            "supported_case_ids": config["supported_case_ids"],
            "source_files": len(construction["files"])}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
