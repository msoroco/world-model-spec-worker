"""Prepare a source-gated alternate four-camera rig for the pedestrian case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIX = "response_siren_pedestrian"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"].endswith("__" + SUFFIX))
    original = json.loads((HERE / entry["construction"]).read_text())
    alternate = json.loads(json.dumps(original))
    runner = next(item for item in alternate["files"] if item["path"] == "runner.py")
    old = 'rig = NativeCameraRig(native_world, ego, carla, reviewed["site"])'
    new = '''site = dict(reviewed["site"])
        alternatives = site.get("fallback_cameras")
        if not isinstance(alternatives, list) or not site.get("fallback_camera_reviewer") or not site.get("fallback_camera_source_citation"):
            raise ValueError("Reviewed alternate camera source missing")
        site["cameras"] = alternatives
        from native_handoff import validate_camera_plan
        validate_camera_plan(site)
        rig = NativeCameraRig(native_world, ego, carla, site)'''
    if runner["content"].count(old) != 1:
        raise ValueError("Native camera binding changed")
    runner["content"] = runner["content"].replace(old, new)
    runner.pop("source", None)
    target = HERE / "constructions" / (SUFFIX + "-fallback1.json")
    target.write_text(json.dumps(alternate, indent=2) + "\n")
    entry["candidates"] = [{
        "id": "fallback1", "construction": target.relative_to(HERE).as_posix(),
        "construction_sha256": sha(target),
        "trigger": {"source": "original four-camera pixel audit and reviewer",
                    "metric": "pedestrian visibility in synchronized overview and reference corner views",
                    "failure_condition": "reviewed original frames show occlusion or unsafe near-field framing"},
        "changed_knobs": ["reviewed fallback_cameras poses, with original profile sizes and source hash"],
    }]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("prepared reviewed-source alternate camera rig candidate")


if __name__ == "__main__":
    main()
