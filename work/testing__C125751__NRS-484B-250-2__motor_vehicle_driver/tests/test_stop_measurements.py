import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stop_measurements import analyze


class StopMeasurementsTests(unittest.TestCase):
    def test_source_join_preserves_stop_and_priority_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stop_context.json").write_text(json.dumps({
                "intersection_id": 7,
                "selected_reference": {"kind": "marked_stop_line", "segment_xy_m": [[-5,-2],[-5,2]]},
                "geometry_source": "synthetic surveyed line", "reference_review_source": "synthetic diagnostic"}))
            history = []
            mapping = []
            for i in range(4):
                frame, t = i+1, i/20
                history.append({"frame": frame, "time_s": t,
                                "ego": {"speed_mps": 0 if i == 1 else 2,
                                        "front_xy_m": [-5 if i == 1 else -5+i, 0],
                                        "body_inside_crossing": i == 3},
                                "other": {"speed_mps": 0 if i == 0 else 2,
                                          "front_xy_m": [0,-5+i],
                                          "body_inside_crossing": i >= 2}})
                mapping.append({"video_frame": i, "carla_frame": frame, "time_s": t})
            def write(name, rows):
                (root / name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
            write("stop_history.jsonl", history)
            write("video_frames.jsonl", mapping)
            entries = {"intersection_id": 7,
                       "first_body_entry": {"ego": {"frame": 4, "time_s": .15},
                                            "other": {"frame": 3, "time_s": .1}}}
            report = analyze(root, entries)
            self.assertEqual(report["first_recorded_zero_speed_before_entry"]["ego"]["frame"], 2)
            self.assertEqual(report["first_recorded_zero_speed_before_entry"]["ego"]["front_distance_to_reference_m"], 0)
            self.assertTrue(report["other_body_inside_at_ego_entry"])
            self.assertEqual(report["statutory_stop_judgment"], "unresolved")
            mapping[2]["time_s"] += .01
            write("video_frames.jsonl", mapping)
            with self.assertRaisesRegex(ValueError, "Original stop/video frame join failed"):
                analyze(root, entries)
            write("video_frames.jsonl", [dict(row, time_s=i/20) for i, row in enumerate(mapping)])
            entries["first_body_entry"]["other"]["time_s"] = .11
            with self.assertRaisesRegex(ValueError, "other stop/entry timestamp mismatch"):
                analyze(root, entries)


if __name__ == "__main__":
    unittest.main()
