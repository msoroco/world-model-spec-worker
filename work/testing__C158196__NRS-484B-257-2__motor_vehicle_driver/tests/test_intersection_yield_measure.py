import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("intersection_yield_measure", ROOT / "intersection_yield_measure.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def body(x):
    return [[x+dx, y] for dx, y in ((-1, -1), (-1, 1), (1, 1), (1, -1))]


def fixture(root, *, other_device="none", stale=False, entering_signal="Off"):
    inventory = {"non_through_highway": True, "all_entrances_inventoried": True,
                 "ego_lane_key": "7:-1", "other_lane_key": "8:-1",
                 "intersection_boundary_source": "native-junction-boundary",
                 "intersection_polygon_xy_m": [[10, -5], [20, -5], [20, 5], [10, 5]],
                 "conflict_point_source": "native-lane-crossing",
                 "complete_body_observation_source": "original-actor-bounds",
                 "entrances": [{"lane_key": "7:-1", "device": "stop", "device_source": "native-sign-facing-7"},
                               {"lane_key": "8:-1", "device": other_device, "device_source": "native-full-approach-inventory"}]}
    (root / "entrance_inventory.json").write_text(json.dumps(inventory) + "\n")
    rows = []
    for i, inside in enumerate((False, False, True, True)):
        rows.append({"frame": 100+i, "time_s": 1+i*0.05, "ego_lane_key": "7:-1",
                     "other_lane_key": "8:-1", "ego_body_vertices_xy_m": body(12 if inside else 0),
                     "other_body_vertices_xy_m": body(13 if i >= 1 else 0),
                     "signal_controls_ego": False, "signal_state": entering_signal,
                     "ego_speed_mps": (3, 0, 2, 2)[i], "other_speed_mps": 4,
                     "ego_distance_to_conflict_m": (8, 7, 5, 3)[i],
                     "other_distance_to_conflict_m": (10, 8, 6, 4)[i]})
    frames = [{"video_frame": i, "carla_frame": r["frame"], "time_s": r["time_s"]}
              for i, r in enumerate(rows)]
    if stale:
        frames[2]["carla_frame"] = 99
    (root / "crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))


class YieldMeasureTests(unittest.TestCase):
    def test_signed_duty_and_continuous_conflict_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            result = measure.analyze(root)
            self.assertTrue(result["signed_duty_candidate"])
            self.assertTrue(result["stopped_before_entry_observed"])
            self.assertTrue(result["other_inside_at_ego_entry"])
            self.assertEqual(result["first_ego_entry_frame"], 102)
            self.assertEqual(result["samples"][2]["other_time_to_conflict_s"], 1.5)
            self.assertEqual(result["immediate_hazard_judgment"], "unresolved")

    def test_missing_source_stale_join_and_signed_other_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, stale=True)
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)
            fixture(root, other_device="yield")
            with self.assertRaisesRegex(ValueError, "non-obligated"):
                measure.analyze(root)
            (root / "entrance_inventory.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original source"):
                measure.analyze(root)

    def test_controlled_signal_suppresses_signed_duty_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, entering_signal="Green")
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            rows[2]["signal_controls_ego"] = True
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            result = measure.analyze(root)
            self.assertTrue(result["operative_signal_controls_ego_at_entry_observed"])
            self.assertFalse(result["signed_duty_candidate"])
            self.assertEqual(result["legal_conclusion"], "unresolved")


if __name__ == "__main__":
    unittest.main()
