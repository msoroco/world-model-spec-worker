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
    def actor(ident, x, y, vx, vy):
        return {"actor_id":ident,"position_xy_m": [x, y], "velocity_xy_mps": [vx, vy],
                "body_vertices_xy_m": [[x-.4, y-.4], [x+.4, y-.4],
                                       [x+.4, y+.4], [x-.4, y+.4]]}
    rows = [
        {"frame": 1, "time_s": 0.05, "ego": actor(10,-5.4, 0, 0, 0),
         "oncoming": actor(11,0, 10, 0, -5),
         "reciprocal":actor(12,0,20,0,-2),"ego_heading_deg":0,
         "ego_left_indicator": True},
        {"frame": 2, "time_s": 0.1, "ego": actor(10,-1, 0, 0, 0),
         "oncoming": actor(11,0, 4, 0, -5),
         "reciprocal":actor(12,0,17,0,-2),"ego_heading_deg":0,
         "ego_left_indicator": True},
        {"frame": 3, "time_s": 0.15, "ego": actor(10,-1, 0, 0, 0),
         "oncoming": actor(11,0, -10, 0, -5),
         "reciprocal":actor(12,0,15,0,-2),"ego_heading_deg":0,
         "ego_left_indicator": True},
        {"frame": 4, "time_s": 0.2, "ego": actor(10,-1, 0, 0, 0),
         "oncoming": actor(11,0, -15, 0, -5),
         "reciprocal":actor(12,0,14,0,0),"ego_heading_deg":-20,
         "ego_left_indicator": True},
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
            self.assertEqual(report['initial_oncoming_clearance_frame'],3)
            self.assertEqual(report['ego_turn_start_frame'],4)
            self.assertTrue(report['reciprocal_stopped_outside_during_turn'])
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

    def test_rejects_missing_later_opposing_actor(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);sources(root)
            rows=[json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines()]
            del rows[2]['reciprocal']
            (root/'interaction_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'Missing participant: reciprocal'):
                MODULE.analyze(root)

    def test_stopped_later_actor_without_prior_approach_is_not_reciprocal_yield(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);sources(root)
            rows=[json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines()]
            for row in rows:row['reciprocal']['velocity_xy_mps']=[0,0]
            (root/'interaction_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertFalse(MODULE.analyze(root)['reciprocal_stopped_outside_during_turn'])

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
