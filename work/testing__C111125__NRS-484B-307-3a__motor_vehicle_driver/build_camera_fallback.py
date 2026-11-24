"""Build one surveyed alternate camera-pose candidate per exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ("dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(path.read_text())
    for row, suffix in zip(manifest["cases"], SUFFIXES):
        primary = json.loads((HERE / row["construction"]).read_text())
        alternate = json.loads(json.dumps(primary))
        files = {item["path"]: item for item in alternate["files"]}
        camera = files["native_cameras.py"]["content"]
        old = 'poses = site.get("camera_poses")'
        if camera.count(old) != 1:
            raise ValueError("primary camera survey selector changed")
        camera = camera.replace(old, 'poses = site.get("alternate_camera_poses")')
        files["native_cameras.py"]["content"] = camera
        config = json.loads(files["config.json"]["content"])
        config["code_sha256"]["native_cameras.py"] = sha(camera.encode())
        config["camera_pose_selection"] = "alternate_source_survey"
        files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
        candidate_path = HERE / ("construction-fallback1-" + suffix + ".json")
        candidate_path.write_text(json.dumps(alternate, indent=2) + "\n")
        row["candidate_risk"] = {
            "status": "physical",
            "reason": "Original circular-green and arrow pixels may be too small or occluded in the primary approach camera; a second independently surveyed pose may make both lamp aspects resolvable without changing the movement or other-user contrast.",
        }
        row["candidates"] = [{
            "id": "fallback1", "construction": candidate_path.name,
            "construction_sha256": sha(candidate_path.read_bytes()),
            "trigger": {"source": "delivery_audit.py and saved original approach-camera PNGs",
                        "metric": "independent dual-lamp pixel resolvability",
                        "failure_condition": "primary approach pixels cannot independently resolve both simultaneously lit aspects"},
            "changed_knobs": ["camera pose source: alternate_camera_poses in source-sealed site.json"],
        }]
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("built", len(SUFFIXES), "source-surveyed camera fallback constructions")


if __name__ == "__main__":
    main()
