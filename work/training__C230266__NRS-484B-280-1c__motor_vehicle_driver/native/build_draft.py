"""Bind the unselected exact-case Native draft to its inline source bytes."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CASE = "training__C230266__NRS-484B-280-1c__motor_vehicle_driver__probe_1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = HERE / "draft-primary"
    files = []
    for name, source in (("runner.py", "runner.py"), ("config.json", "config.json"),
                         ("tests/test_offline.py", "test_offline.py")):
        files.append({"path": name, "content": (folder / source).read_text()})
    construction = {
        "format": "worker-inline-construction", "case_id": CASE,
        "law_id": "NRS-484B-280-1c", "cell_id": "C230266",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
        "recording_description": {
            "duration_s": 30, "rate_hz": 20,
            "source_cameras": ["overview", "ego_front", "pedestrian_side", "traffic_rear"],
            "channels": [
                {"name": "native_vehicle_pedestrian_pose_and_control",
                 "method": "Native actor transform, velocity and requested control at 20 Hz",
                 "sampling_rate_hz": 20, "time_window": "600 frames"},
                {"name": "four_camera_video", "method": "four synchronized named RGB source cameras",
                 "sampling_rate_hz": 20, "time_window": "600 frames"}],
            "limitations": ["Actual driver observation is not inferred from visibility or requested control",
                            "Original road survey, Native motion and camera pixels remain unverified"]},
        "status": "draft_cpu_offline_only"}
    construction_path = HERE / "unselected-road-pedestrian-construction.json"
    construction_path.write_text(json.dumps(construction, indent=2) + "\n")
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ROOT.name, "status": "draft_not_selected",
                "cases": [{"case_id": CASE,
                           "construction": "native/unselected-road-pedestrian-construction.json",
                           "construction_sha256": sha(construction_path), "candidates": [],
                           "candidate_risk": {"status": "physical",
                                              "reason": "Pedestrian spawn, actual observation and camera framing need Native review."}}],
                "original_native_observed": False, "delivery_ready": False}
    (ROOT / "draft-road-pedestrian-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"construction_sha256": sha(construction_path),
                      "manifest_sha256": sha(ROOT / "draft-road-pedestrian-manifest.json")}))


if __name__ == "__main__":
    main()
