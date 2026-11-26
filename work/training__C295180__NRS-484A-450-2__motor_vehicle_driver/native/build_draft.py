"""Build two exact unselected stop-line inline constructions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASES = {"condition_a": "full_stop", "condition_b": "rolling"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries = []
    for condition, stop_policy in CASES.items():
        case = ASSIGNMENT + "__selected_ef239a06__" + condition
        config = {"case_id": case, "selected_case_id": case,
                  "law_id": "NRS-484A-450-2", "cell_id": "C295180",
                  "actor": "motor_vehicle_driver", "rate_hz": 20,
                  "duration_s": 30, "duration_frames": 600,
                  "cameras": [{"name": name, "fps": 20, "width": width,
                               "height": height} for name, width, height in (
                                   ("overview", 1920, 1080),
                                   ("approach", 1280, 720),
                                   ("reference_corner", 1280, 720),
                                   ("driver_reference", 1280, 720))],
                  "stop_policy": stop_policy, "stop_sign_governs": True,
                  "near_crosswalk_present": False, "marked_stop_line_x_m": 0,
                  "front_body_offset_m": 2.0,
                  "physical_verified": False, "legal_verdict": None}
        construction = {"format": "worker-inline-construction", "case_id": case,
                        "cell_id": "C295180", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": [
                            {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                            {"path": "runner.py", "content": (HERE / "draft_runner.py").read_text()},
                            {"path": "tests/test_offline.py", "content":
                             (HERE / "test_draft_offline.py").read_text()},
                            *[{"path": name, "content": (HERE / name).read_text()}
                              for name in ("road_source.py", "authored-road.xodr",
                                           "stop_line_request.py", "saved_stop_line.py",
                                           "live_capture.py")]],
                        "recording_description": {"channels": [
                            {"name": "raw_ego_motion", "method": "original actor velocity and footprint",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "applicable_stop_reference", "method": "original crosswalk/line/sign map readback",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "four_camera_video", "method": "four named source streams",
                             "sampling_rate_hz": 20, "time_window": "600 frames"}],
                            "limitations": ["Native sign/line rendering and original pixels unverified"]},
                        "status": "exact_unselected_offline_draft"}
        path = HERE / (condition + "-construction.json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        entries.append({"case_id": case, "construction": path.name,
                        "construction_sha256": sha(path)})
    manifest = {"format": "draft-execution-manifest", "cases": entries}
    (HERE / "draft-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
