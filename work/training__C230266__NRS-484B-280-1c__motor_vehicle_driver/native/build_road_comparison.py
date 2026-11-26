"""Build exact offline Native drafts for both road-position caution requests."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
OLD = f"{ASSIGNMENT}__probe_1"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(case_number):
    cid = f"{ASSIGNMENT}__probe_{case_number}"
    target = HERE / f"road-probe-{case_number}"
    target.mkdir(exist_ok=True)
    source = HERE / "draft-primary"
    runner = (source / "runner.py").read_text().replace(OLD, cid)
    runner = runner.replace('"ego_front", "pedestrian_side", "traffic_rear"',
                            '"approach", "reference_corner", "driver_reference"')
    if case_number == 2:
        runner = runner.replace('"distance_triggered_slow_request"', '"maintain_approach_request"')
        runner = runner.replace('if distance_m < 18:', 'if False and distance_m < 18:')
    (target / "runner.py").write_text(runner)
    config = json.loads((source / "config.json").read_text())
    config["case_id"] = cid
    config["selected_case_id"] = cid
    config["controller"] = "distance_triggered_slow_request" if case_number == 1 else "maintain_approach_request"
    config["status"] = "road_comparison_cpu_draft"
    for camera, name in zip(config["cameras"], CAMERAS):
        camera["name"] = name
        camera["pose_strategy"] = "ego_relative_source_camera"
    (target / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    test = (source / "test_offline.py").read_text()
    if case_number == 2:
        test = test.replace('self.assertEqual(control(10, 8)["phase"], "slow_request")',
                            'self.assertEqual(control(10, 8)["phase"], "approach_request")')
    (target / "test_offline.py").write_text(test)
    construction = {
        "format": "worker-inline-construction", "case_id": cid,
        "law_id": "NRS-484B-280-1c", "cell_id": "C230266", "actor": "motor_vehicle_driver",
        "entrypoint": "runner.py",
        "files": [{"path": ("tests/test_offline.py" if name == "test_offline.py" else name),
                   "content": (target / name).read_text()}
                  for name in ("runner.py", "config.json", "test_offline.py")],
        "recording_description": {
            "duration_s": 30, "rate_hz": 20, "source_cameras": list(CAMERAS),
            "channels": [
                {"name": "native_vehicle_pedestrian_pose_and_control",
                 "method": "Native actor transform, velocity and requested control at 20 Hz",
                 "sampling_rate_hz": 20, "time_window": "600 frames"},
                {"name": "four_camera_video", "method": "four synchronized named RGB source cameras",
                 "sampling_rate_hz": 20, "time_window": "600 frames"}],
            "limitations": ["Actual driver observation is not inferred from visibility or requested control",
                            "Original road survey, Native motion and camera pixels remain unverified"]},
        "status": "cpu_offline_draft"}
    path = HERE / f"road-probe-{case_number}-construction.json"
    path.write_text(json.dumps(construction, indent=2) + "\n")
    return {"case_id": cid, "construction": str(path.relative_to(ROOT)),
            "construction_sha256": sha(path), "candidates": [],
            "candidate_risk": {"status": "physical", "reason": "Roadside pedestrian spawn and visibility require original Native survey and physical review."}}


def main():
    cases = [materialize(i) for i in (1, 2)]
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "draft_not_selected",
                "cases": cases, "original_native_observed": False, "delivery_ready": False}
    path = ROOT / "draft-road-pedestrian-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case_ids": [c["case_id"] for c in cases], "manifest_sha256": sha(path)}))


if __name__ == "__main__":
    main()
