"""Synthetic source-shape tests for saved processing, not original evidence."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

NATIVE = Path(__file__).resolve().parents[1] / "native"
sys.path.insert(0, str(NATIVE))
from finalize_rider import CAMERAS, finalize, sha256
from audit_comparison import audit
from scene import fixed_context

SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c136495-temp"


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def fixture(folder: Path, condition: str) -> None:
    actor_rows = []
    camera_rows = []
    for index in range(600):
        frame = 1000 + index
        ego_y = -1.58 if condition == "intrusion" and 200 <= index < 400 else -1.1
        rider_speed = 3.8 if condition == "intrusion" and index >= 220 else 4.0
        actor_rows.append({"native_frame": frame, "time_s": index / 20,
                           "actors": {"ego": {"x_m": 5 + index * .35, "y_m": ego_y},
                                      "rider": {"x_m": 40 + index * .2,
                                                "y_m": -2.48, "speed_mps": rider_speed,
                                                "yaw_rad": 0.0}}})
        camera_rows.append({"native_frame": frame, "time_s": index / 20,
                            "camera_frames": {name: frame for name in CAMERAS}})
    (folder / "actor-frames.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in actor_rows))
    (folder / "camera-frame-map.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in camera_rows))
    write_json(folder / "classification.json", {
        "driver_actor_role": "motor_vehicle_driver", "rider_vehicle_type": "bicycle",
        "rider_lawful_status": "unresolved", "driver_intent": "unresolved",
        "observed_body_width_m": {"ego": 1.8, "rider": .6},
        "observed_body_length_m": {"ego": 4.3, "rider": 1.8}})
    files = ("actor-frames.jsonl", "camera-frame-map.jsonl", "classification.json")
    write_json(folder / "rider-binding.json", {
        "format": "c136495-native-source-manifest-v1", "condition": condition,
        "candidate_id": "primary",
        "fixed_context": fixed_context(),
        "case_id": "training__C136495__NRS-484B-270-1__motor_vehicle_driver__probe_" +
                   ("a" if condition == "clear" else "b"),
        "sha256": {name: sha256(folder / name) for name in files}})


def rehash(folder: Path, name: str) -> None:
    path = folder / "rider-binding.json"
    manifest = json.loads(path.read_text())
    manifest["sha256"][name] = sha256(folder / name)
    write_json(path, manifest)


class SavedSourceTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.folder = Path(self.temp.name)
        fixture(self.folder, "intrusion")

    def tearDown(self):
        self.temp.cleanup()

    def test_two_positive_conditions_are_measurements_only(self):
        intrusion = finalize(self.folder)
        self.assertEqual(intrusion["frame_count"], 600)
        self.assertEqual(intrusion["first_ego_lateral_change_frame"], 1200)
        self.assertEqual(intrusion["first_rider_speed_drop_frame"], 1220)
        self.assertEqual(intrusion["driver_intent"], "unresolved")
        self.assertEqual(intrusion["causal_interference"], "unresolved")
        self.assertFalse(intrusion["physical_native_verified"])
        fixture(self.folder, "clear")
        clear = finalize(self.folder)
        self.assertIsNone(clear["first_ego_lateral_change_frame"])
        self.assertIsNone(clear["first_rider_speed_drop_frame"])
        self.assertGreater(clear["minimum_lateral_surface_gap_m"],
                           intrusion["minimum_lateral_surface_gap_m"])

    def test_stale_actor_source_rejected(self):
        with (self.folder / "actor-frames.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            finalize(self.folder)

    def test_missing_camera_source_rejected(self):
        path = self.folder / "camera-frame-map.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[10]["camera_frames"].pop("reference_corner")
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        rehash(self.folder, path.name)
        with self.assertRaisesRegex(ValueError, "camera sources missing"):
            finalize(self.folder)

    def test_changed_frame_identity_rejected(self):
        path = self.folder / "actor-frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[10]["native_frame"] = 9999
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        rehash(self.folder, path.name)
        with self.assertRaisesRegex(ValueError, "frame join differs"):
            finalize(self.folder)

    def test_claimed_intent_rejected(self):
        path = self.folder / "classification.json"
        data = json.loads(path.read_text())
        data["driver_intent"] = "intentional"
        write_json(path, data)
        rehash(self.folder, path.name)
        with self.assertRaisesRegex(ValueError, "intent assertion"):
            finalize(self.folder)

    def test_no_longitudinal_interaction_rejected(self):
        path = self.folder / "actor-frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row["actors"]["rider"]["x_m"] += 500
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        rehash(self.folder, path.name)
        with self.assertRaisesRegex(ValueError, "interaction window"):
            finalize(self.folder)

    def test_comparison_source_isolation_and_negative(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as clear_name:
            clear = Path(clear_name)
            fixture(clear, "clear")
            passed = audit(clear, self.folder)
            self.assertFalse(passed["physical_acceptance_claimed"])
            self.assertEqual(len(passed["case_ids"]), 2)
            with self.assertRaisesRegex(ValueError, "condition or ordering"):
                audit(self.folder, clear)
            manifest_path = clear / "rider-binding.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["candidate_id"] = "fallback1"
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "candidate engineering"):
                audit(clear, self.folder)
            manifest["candidate_id"] = "primary"
            manifest["fixed_context"]["duration_s"] = 10
            write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "fixed context"):
                audit(clear, self.folder)


if __name__ == "__main__":
    unittest.main()
