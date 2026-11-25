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
                  "candidate_id": "primary",
                  "required_atoms": ["kin.position", "kin.speed"],
                  "cameras": [{"name": name, "fps": 20, "width": width,
                               "height": height} for name, width, height in (
                                   ("overview", 1920, 1080),
                                   ("approach", 1280, 720),
                                   ("reference_corner", 1280, 720),
                                   ("driver_reference", 1280, 720))],
                  "condition": condition, "entry_release_s": release, "lead_conflict_s": 12,
                  "follower_conflict_s": 24,
                  "control_phases": ["approach", "entry_wait", "circulation"],
                  "source_actor_ids": ["ego", "lead", "follower"],
                  "recording_description": {"channels": [
                      {"name": name, "unit": "structured", "sampling_rate_hz": 20,
                       "time_window": "600 original frames", "method": "source-joined Native readback",
                       "reference_frame": "original Native frame and simulation time",
                       "uncertainty": "50 ms cadence; physical identity and pixels need review"}
                      for name in ("raw_ego_motion", "raw_circulating_motion", "frame_join")],
                      "context_inputs": [{"name": "roundabout_map", "unit": "source_record",
                                          "method": "Native map readback and road.xodr"}],
                      "limitations": ["Original motion and pixels require physical review"]},
                  "physical_verified": False, "legal_verdict": None}
        construction = {"format": "worker-inline-construction", "case_id": case,
                        "cell_id": "C239014", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": [
                            {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                            {"path": "runner.py", "content": (HERE / "runner.py").read_text()},
                            {"path": "geometry.py", "content": (HERE / "geometry.py").read_text()},
                            {"path": "finalize.py", "content": (HERE / "finalize.py").read_text()},
                            {"path": "tests/test_offline.py", "content":
                             (HERE / "test_draft_offline.py").read_text()},
                            {"path": "tests/test_native.py", "content":
                             (HERE / "tests/test_native.py").read_text()}],
                        "recording_description": config["recording_description"],
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
