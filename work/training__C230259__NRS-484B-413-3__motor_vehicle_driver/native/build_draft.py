"""Build an exact, unselected inline construction for offline testing."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
assignment = "training__C230259__NRS-484B-413-3__motor_vehicle_driver"
case = assignment + "__probe_1"
config = {"case_id": case, "selected_case_id": case, "law_id": "NRS-484B-413-3",
          "cell_id": "C230259", "actor": "motor_vehicle_driver", "rate_hz": 20,
          "duration_s": 30, "duration_frames": 600,
          "cameras": [{"name": name, "fps": 20, "width": width, "height": height}
                      for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                                  ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
          "follower_policy": "same_lane_behind_source_measured",
          "control_phases": [{"name": "approach", "first_frame": 0, "last_frame": 149, "signal_request": "none"},
                             {"name": "prior_signal", "first_frame": 150, "last_frame": 199,
                              "signal_request": "brake_lamp"},
                             {"name": "slow", "first_frame": 200, "last_frame": 599,
                              "signal_request": "brake_lamp"}],
          "physical_verified": False, "legal_verdict": None}
construction = {"format": "worker-inline-construction", "case_id": case,
                "cell_id": "C230259", "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                "files": [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                          {"path": "runner.py", "content": (here / "draft_runner.py").read_text()},
                          {"path": "tests/test_offline.py", "content": (here / "test_draft_offline.py").read_text()}],
                "recording_description": {"channels": [
                    {"name": "raw_ego_and_rear_motion", "method": "Native velocity, transforms and bounding boxes",
                     "sampling_rate_hz": 20, "time_window": "600 frames"},
                    {"name": "raw_signal_state", "method": "Native control request plus original lamp observation",
                     "sampling_rate_hz": 20, "time_window": "600 frames"},
                    {"name": "four_camera_video", "method": "four named source cameras",
                     "sampling_rate_hz": 20, "time_window": "600 frames"}],
                    "limitations": ["Native route and actual camera pixels unverified"]},
                "status": "draft_cpu_offline_only"}
path = here / "draft-prior-construction.json"
path.write_text(json.dumps(construction, indent=2) + "\n")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {"format": "draft-execution-manifest", "cases": [{"case_id": case,
             "construction": "draft-prior-construction.json", "construction_sha256": digest}]}
(here / "draft-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"construction_sha256": digest}))
