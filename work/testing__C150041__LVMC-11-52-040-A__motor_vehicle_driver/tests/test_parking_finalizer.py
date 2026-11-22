"""Saved-only history must be original, ordered and stationary."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_finalizer import finalize
from parking_pose import construct
from source_review import validate
from test_source_review import fixture


def write_history(root, pose, speeds):
    path = Path(root) / "original-history.jsonl"
    frames = [{"frame": index, "time_s": index * .05,
               "body_vertices_xy_m": pose["target_body_vertices_xy_m"],
               "vehicle_forward_xy": pose["target_forward_xy"],
               "speed_m_s": speed,
               "control": {"throttle": 0, "steer": 0, "brake": 1}}
              for index, speed in enumerate(speeds)]
    path.write_text("".join(json.dumps(frame) + "\n" for frame in frames))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class ParkingFinalizerTests(unittest.TestCase):
    def test_hashed_original_hold_and_activity_binding(self):
        with TemporaryDirectory() as tmp:
            packet_path, _ = fixture(tmp)
            pose = construct(validate(packet_path, source_root=tmp), "park_parallel_lawful")
            history, digest = write_history(tmp, pose, [2, .2, .1, 0, 0])
            result = finalize(packet_path, tmp, "park_parallel_lawful", history, digest)
            self.assertEqual(result["stationary_intervals"],
                             [{"first_frame": 2, "last_frame": 4, "duration_s": .1}])
            self.assertEqual(len(result["observations"]), 5)
            self.assertEqual(result["observations"][2]["body_corners_inside_roadway"], 4)
            self.assertEqual(result["legal_judgment"], "unresolved")
            self.assertFalse(result["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "activity differs"):
                finalize(packet_path, tmp, "stand_parallel_lawful", history, digest)
            history.write_text(history.read_text() + "{}\n")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                finalize(packet_path, tmp, "park_parallel_lawful", history, digest)

    def test_missing_hold_and_original_control_rejected(self):
        with TemporaryDirectory() as tmp:
            packet_path, _ = fixture(tmp)
            pose = construct(validate(packet_path, source_root=tmp), "park_parallel_lawful")
            history, digest = write_history(tmp, pose, [2, 1, 2])
            with self.assertRaisesRegex(ValueError, "lacks a multi-frame"):
                finalize(packet_path, tmp, "park_parallel_lawful", history, digest)
            history, _ = write_history(tmp, pose, [0, 0])
            lines = [json.loads(line) for line in history.read_text().splitlines()]
            del lines[0]["control"]
            history.write_text("".join(json.dumps(line) + "\n" for line in lines))
            digest = hashlib.sha256(history.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "control fields missing"):
                finalize(packet_path, tmp, "park_parallel_lawful", history, digest)


if __name__ == "__main__":
    unittest.main()
