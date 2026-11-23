import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("analyze_source", ROOT / "analyze_source.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedAnalysisTests(unittest.TestCase):
    def make_attempt(self, root):
        packet = {"map_name": "Town", "map_sha256": "a" * 64,
                  "crosswalk_source": "native:marking/1",
                  "crosswalk_polygon_xy": [[0, 0], [2, 0], [2, 4], [0, 4]],
                  "vehicle_blueprint_id": "vehicle.car", "spawn_transform_source": "native:waypoint/2",
                  "reverse_route_xy": [[5, 2], [1, 2]], "driver_source": "native:ego/4",
                  "district_source": "map:residential/1"}
        body = [[1.5, 1], [2.5, 1], [2.5, 2], [1.5, 2]]
        frame = {"frame": 0, "time_s": 0, "vehicle_actor_id": 4,
                 "body_polygon_xy": body, "crosswalk_polygon_xy": packet["crosswalk_polygon_xy"],
                 "velocity_xy": [-1, 0], "forward_xy": [1, 0], "reverse_gear": True}
        path = root / "channels" / "reverse-body-crosswalk.jsonl"
        path.parent.mkdir()
        path.write_text(json.dumps(frame) + "\n")
        context = {"map_packet": packet, "frames_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "source_id": "fixture-only", "vehicle_actor_id": 4}
        (root / "reviewed-crosswalk-source.json").write_text(json.dumps(context) + "\n")
        return path

    def test_positive_and_negative_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            frames = self.make_attempt(root)
            report = module.analyze(root, expected_relation="overlap")
            self.assertEqual(report["measurements"]["crosswalk_relation"]["observed_relation"], "overlap")
            with self.assertRaises(ValueError):
                module.analyze(root, expected_relation="contact")
            frames.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                module.analyze(root, expected_relation="overlap")

    def test_reject_source_hash_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            frames = self.make_attempt(root)
            frames.write_text(frames.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                module.analyze(root, expected_relation="overlap")


if __name__ == "__main__":
    unittest.main()
