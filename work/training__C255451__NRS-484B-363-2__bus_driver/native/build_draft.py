"""Build two exact unselected school-crossing speed constructions."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
CASES = {"condition_a": 20, "condition_b": 30}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries = []
    for condition, speed in CASES.items():
        case = ASSIGNMENT + "__selected_d08892c9__" + condition
        config = {"case_id": case, "selected_case_id": case,
                  "law_id": "NRS-484B-363-2", "cell_id": "C255451",
                  "actor": "bus_driver", "rate_hz": 20,
                  "duration_s": 30, "duration_frames": 600,
                  "cameras": [{"name": name, "fps": 20, "width": width,
                               "height": height} for name, width, height in (
                                   ("overview", 1920, 1080),
                                   ("approach", 1280, 720),
                                   ("reference_corner", 1280, 720),
                                   ("driver_reference", 1280, 720))],
                  "speed_request_mph": speed, "zone_start_x_m": 100,
                  "zone_end_x_m": 200,
                  "source_actor_ids": ["bus", "child_left", "child_right"],
                  "calendar_verified": False, "beacon_verified": False,
                  "physical_verified": False, "legal_verdict": None}
        construction = {"format": "worker-inline-construction", "case_id": case,
                        "cell_id": "C255451", "actor": "bus_driver",
                        "entrypoint": "runner.py", "files": [
                            {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                            {"path": "runner.py", "content": (HERE / "draft_runner.py").read_text()},
                            {"path": "tests/test_offline.py", "content":
                             (HERE / "test_draft_offline.py").read_text()}],
                        "recording_description": {"channels": [
                            {"name": "raw_bus_motion", "method": "original bus actor readback",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "signed_zone_context", "method": "source-hashed sign and road-zone boundaries",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "child_actor_context", "method": "original child actor readback",
                             "sampling_rate_hz": 20, "time_window": "600 frames"},
                            {"name": "four_camera_video", "method": "four named source streams",
                             "sampling_rate_hz": 20, "time_window": "600 frames"}],
                            "limitations": ["Native zone, original pixels and exception timing unverified"]},
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
