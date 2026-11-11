import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("measurements", PACKAGE / "measurements.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sources(root):
    (root / "intersection_geometry.json").write_text(json.dumps({
        "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
        "conflict_point_xy_m": [0, 0],
        "oncoming_direction_xy": [0, -1],
        "ego_intended_maneuver": "left_turn",
    }))
    def actor(x, y, vx, vy):
        return {"position_xy_m": [x, y], "velocity_xy_mps": [vx, vy],
                "body_vertices_xy_m": [[x-.4, y-.4], [x+.4, y-.4],
                                       [x+.4, y+.4], [x-.4, y+.4]]}
    rows = [
        {"frame": 1, "time_s": 0.05, "ego": actor(-5.4, 0, 0, 0),
         "oncoming": actor(0, 10, 0, -5), "ego_left_indicator": True},
        {"frame": 2, "time_s": 0.1, "ego": actor(-1, 0, 0, 0),
         "oncoming": actor(0, 4, 0, -5), "ego_left_indicator": True},
    ]
    (root / "interaction_history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": i, "carla_frame": r["frame"], "time_s": r["time_s"]
    }) + "\n" for i, r in enumerate(rows)))


class MeasurementsTest(unittest.TestCase):
    def test_opposing_entry_and_kinematic_time(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            sources(root)
            report = MODULE.analyze(root)
            self.assertEqual(report["ego_first_in_intersection_frame"], 1)
            self.assertEqual(report["oncoming_first_in_intersection_frame"], 2)
            self.assertEqual(report["opposing_conflict_samples"][0]["kinematic_time_to_conflict_s"], 2)
            self.assertIn("unresolved", report["judgment_unresolved"])

    def test_rejects_missing_raw_source(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            sources(root)
            (root / "interaction_history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: interaction_history.jsonl"):
                MODULE.analyze(root)

    def test_rejects_missing_indicator_observation(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            sources(root)
            rows = [json.loads(line) for line in (root / "interaction_history.jsonl").read_text().splitlines()]
            del rows[0]["ego_left_indicator"]
            (root / "interaction_history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            with self.assertRaisesRegex(ValueError, "Missing measured left-indicator state"):
                MODULE.analyze(root)

    def test_rejects_frame_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            sources(root)
            rows = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            rows[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            with self.assertRaisesRegex(ValueError, "Original frame/time join failed"):
                MODULE.analyze(root)


if __name__ == "__main__":
    unittest.main()
