"""Build exact unselected inline constructions for two controlled conditions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASES = {"condition_a": 17.0, "condition_b": 12.5}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries = []
    for condition, release in CASES.items():
        case = ASSIGNMENT + "__selected_a60a4f45__" + condition
        config = {"case_id": case, "selected_case_id": case,
                  "law_id": "LVMC-11-43-010-B", "cell_id": "C239014",
                  "actor": "motor_vehicle_driver", "rate_hz": 20,
                  "duration_s": 30, "duration_frames": 600,
                  "cameras": [{"name": name, "fps": 20, "width": width,
                               "height": height} for name, width, height in (
                                   ("overview", 1920, 1080),
                                   ("approach", 1280, 720),
                                   ("reference_corner", 1280, 720),
                                   ("driver_reference", 1280, 720))],
                  "entry_release_s": release, "lead_conflict_s": 12,
                  "follower_conflict_s": 24,
                  "control_phases": ["approach", "entry_wait", "circulation"],
                  "source_actor_ids": ["ego", "lead", "follower"],
                  "physical_verified": False, "legal_verdict": None}
        construction = {"format": "worker-inline-construction", "case_id": case,
                        "cell_id": "C239014", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": [
                            {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                            {"path": "runner.py", "content": (HERE / "draft_runner.py").read_text()},
                            {"path": "tests/test_offline.py", "content":
                             (HERE / "test_draft_offline.py").read_text()}],
                        "recording_description": {"channels": [
                            {"name": "raw_ego_motion", "method": "original actor and frame readback",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "raw_circulating_motion", "method": "two original actor readbacks",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "four_camera_video", "method": "four named source streams",
                             "sampling_rate_hz": 20, "time_window": "600 frames"}],
                            "limitations": ["Native route, original source capture and pixels unverified"]},
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
