"""Synthetic saved-source tests; no CARLA motion or due-care finding."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
import finalize_due_care
from cyclist_response import response_command
from scene import fixed_context

SCRATCH = Path(".runtime-work/c136495-5a-tests")


def _write(folder, name, value):
    path = folder / name
    if name.endswith(".jsonl"):
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in value))
    else:
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(folder, condition):
    suffix = "condition_a" if condition == "early_response" else "condition_b"
    rows, cameras, controls = [], [], []
    for i in range(600):
        frame = i + 100
        t = i / 20
        ego = {"actor_id": 10, "x_m": 5 + 5 * t, "y_m": -1.1,
               "vx_mps": 5, "vy_mps": 0, "body_length_m": 4.8,
               "body_width_m": 1.9}
        rider = {"actor_id": 11, "x_m": 40 + 4 * t, "y_m": -2.48,
                 "vx_mps": 4, "vy_mps": 0, "body_length_m": 1.7,
                 "body_width_m": .55}
        rows.append({"native_frame": frame, "time_s": t,
                     "actors": {"ego": ego, "rider": rider}})
        cameras.append({"native_frame": frame, "time_s": t,
                        "camera_frames": {name: frame for name in finalize_due_care.CAMERAS}})
        prior_t = max(0, i - 1) / 20
        gap = (40 + 4 * prior_t) - (5 + 5 * prior_t) - (
            ego["body_length_m"] + rider["body_length_m"]) / 2
        controls.append({"native_frame": frame, "time_s": t,
                         "condition": condition,
                         "source_forward_gap_m": gap,
                         "source_ego_speed_mps": ego["vx_mps"],
                         "command": response_command(condition, gap, ego["vx_mps"])})
    classification = {"driver_actor_role": "motor_vehicle_driver",
                      "requested_rider_vehicle_type": "bicycle",
                      "actual_person_riding": "unresolved",
                      "wheel_configuration": "unresolved",
                      "propulsion": "unresolved", "moped_exclusion": "unresolved",
                      "due_care": "unresolved", "native_wheel_radii_m": [.32, .32]}
    hashes = {
        "actor-frames.jsonl": _write(folder, "actor-frames.jsonl", rows),
        "camera-frame-map.jsonl": _write(folder, "camera-frame-map.jsonl", cameras),
        "response-control.jsonl": _write(folder, "response-control.jsonl", controls),
        "classification.json": _write(folder, "classification.json", classification),
        "collision-events.jsonl": _write(folder, "collision-events.jsonl", []),
    }
    _write(folder, "rider-binding.json", {
        "format": "c136495-native-source-manifest-v1",
        "condition": condition, "candidate_id": "primary",
        "case_id": finalize_due_care.ASSIGNMENT + "__selected_a21cf01e__" + suffix,
        "fixed_context": fixed_context(), "sha256": hashes,
    })


class SavedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SCRATCH.mkdir(parents=True, exist_ok=True)

    def test_both_condition_sources_measure_without_legal_claim(self):
        for condition in ("early_response", "later_response"):
            with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
                folder = Path(dirname)
                make_fixture(folder, condition)
                result = finalize_due_care.finalize(folder)
                self.assertEqual(result["frame_count"], 600)
                self.assertEqual(result["condition"], condition)
                self.assertEqual(result["collision_sensor_event_count"], 0)
                self.assertGreater(result["requested_braking_frames"], 0)
                self.assertFalse(result["person_riding_bicycle_verified"])
                self.assertFalse(result["legal_verdict_claimed"])

    def test_missing_collision_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
            folder = Path(dirname)
            make_fixture(folder, "early_response")
            (folder / "collision-events.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original source"):
                finalize_due_care.finalize(folder)

    def test_stale_classification_and_unsupported_judgment_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
            folder = Path(dirname)
            make_fixture(folder, "later_response")
            path = folder / "classification.json"
            row = json.loads(path.read_text())
            row["due_care"] = "satisfied"
            _write(folder, "classification.json", row)
            with self.assertRaisesRegex(ValueError, "hash differs"):
                finalize_due_care.finalize(folder)
            binding = json.loads((folder / "rider-binding.json").read_text())
            binding["sha256"]["classification.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
            _write(folder, "rider-binding.json", binding)
            with self.assertRaisesRegex(ValueError, "Unsupported physical or due-care"):
                finalize_due_care.finalize(folder)

    def test_missing_camera_and_time_join_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
            folder = Path(dirname)
            make_fixture(folder, "early_response")
            cameras = [json.loads(line) for line in (folder / "camera-frame-map.jsonl").read_text().splitlines()]
            cameras[42]["camera_frames"].pop("approach")
            digest = _write(folder, "camera-frame-map.jsonl", cameras)
            binding = json.loads((folder / "rider-binding.json").read_text())
            binding["sha256"]["camera-frame-map.jsonl"] = digest
            _write(folder, "rider-binding.json", binding)
            with self.assertRaisesRegex(ValueError, "Four original cameras"):
                finalize_due_care.finalize(folder)

    def test_response_command_tampering_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
            folder = Path(dirname)
            make_fixture(folder, "early_response")
            controls = [json.loads(line) for line in (folder / "response-control.jsonl").read_text().splitlines()]
            controls[200]["command"]["brake"] = 0
            digest = _write(folder, "response-control.jsonl", controls)
            binding = json.loads((folder / "rider-binding.json").read_text())
            binding["sha256"]["response-control.jsonl"] = digest
            _write(folder, "rider-binding.json", binding)
            with self.assertRaisesRegex(ValueError, "response command differs"):
                finalize_due_care.finalize(folder)


if __name__ == "__main__":
    unittest.main()
