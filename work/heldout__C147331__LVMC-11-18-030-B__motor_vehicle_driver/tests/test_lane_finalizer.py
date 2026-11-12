import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runtime_path = Path(__file__).resolve().parents[3] / "runtime" / "scenario_pipeline"
if runtime_path.is_dir():
    sys.path.insert(0, str(runtime_path))
from lane_finalizer import analyze, build_result


CASE = "heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__within_marked_lane"


def write_sources(root):
    config = {"selected_case_id": CASE, "law_id": "LVMC-11-18-030-B",
              "cell_id": "C147331", "actor": "motor_vehicle_driver",
              "case": {"recording_description": {"channels": []}}}
    (root / "config.json").write_text(json.dumps(config))
    mapping, trace, lane = [], [], []
    for index in range(3):
        frame, time_s = 10 + index, (index + 1) / 20
        mapping.append({"video_frame": index, "carla_frame": frame, "time_s": time_s})
        trace.append({"frame": frame, "time_s": time_s})
        lane.append({"frame": frame, "time_s": time_s, "ego_id": 1,
                     "ego_corners_xy_m": [[-0.5, -0.5], [0.5, -0.5],
                                          [0.5, 0.5], [-0.5, 0.5]],
                     "ego_velocity_xy_mps": [0.0, 0.0],
                     "ego_light_state": None,
                     "overtaken_id": None,
                     "overtaken_corners_xy_m": None,
                     "overtaken_velocity_xy_mps": None,
                     "lane": {"polygon_xy_m": [[-2, -1.5], [2, -1.5],
                                               [2, 1.5], [-2, 1.5]],
                              "road_id": 7, "lane_id": 1,
                              "left_marking": "Solid", "right_marking": "Broken"}})
    for name, rows in (("video_frames.jsonl", mapping), ("trace.jsonl", trace),
                       ("marked_lane_sources.jsonl", lane)):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    return lane


class SavedLaneFinalizerTests(unittest.TestCase):
    def test_positive_original_source_and_native_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_sources(root)
            report = analyze(root)
            result = build_result(root, report)
            self.assertEqual(report["case_id"], CASE)
            self.assertEqual(len(report["measurements"]["lane_boundary_observation"]["value"]["frames"]), 3)
            control = report["measurements"]["turn_preparation_control"]
            self.assertEqual(control["method"], "measure_turn_preparation_context")
            self.assertEqual(len(control["value"]["frames"]), 3)
            self.assertEqual(control["value"]["frames"][0]["ego_light_state"], None)
            self.assertFalse(control["value"]["lawful_turn_preparation_confirmed"])
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(len((root / "lane_clearance_m.jsonl").read_text().splitlines()), 3)
            self.assertEqual(analyze(root, write_channel=False)["measurements"], report["measurements"])
            from worker_exchange.native_output import validate_result
            validate_result(result)

    def test_missing_source_and_frame_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = write_sources(root)
            (root / "marked_lane_sources.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: marked_lane_sources.jsonl"):
                analyze(root)
            (root / "marked_lane_sources.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            rows[1]["frame"] = 99
            (root / "marked_lane_sources.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "source/frame-map join failed"):
                analyze(root)


if __name__ == "__main__":
    unittest.main()
