import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("entry_measurements", PACKAGE / "entry_measurements.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_sources(root):
    (root / "road_geometry.json").write_text(json.dumps({
        "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
        "intersection_id": "junction-1", "ego_highway_id": "east-west",
        "other_highway_id": "north-south", "device_inventory_source": "native-map-audit",
        "ego_approach_heading_deg": 0, "other_approach_heading_deg": -90,
        "approach_geometry_source": "synthetic waypoint-pair fixture",
        "ego_approach_origin_xy_m": [-8, 0],
        "other_approach_origin_xy_m": [0, 8],
    }))
    def actor(x, y):
        return {"position_xy_m": [x, y], "body_vertices_xy_m": [
            [x-.3, y-.3], [x+.3, y-.3], [x+.3, y+.3], [x-.3, y+.3]]}
    rows = [
        {"frame": 10, "time_s": .5, "ego": actor(-8, 0), "other": actor(0, 8)},
        {"frame": 11, "time_s": .55, "ego": actor(-5.2, 0), "other": actor(0, 8)},
        {"frame": 12, "time_s": .6, "ego": actor(-4, 0), "other": actor(0, 5.2)},
    ]
    (root / "crossing_history.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": i, "carla_frame": r["frame"], "time_s": r["time_s"]
    }) + "\n" for i, r in enumerate(rows)))


class EntryMeasurementsTest(unittest.TestCase):
    def test_entry_uses_body_and_retains_timing_without_legal_cutoff(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            write_sources(root)
            report = MODULE.analyze(root)
            self.assertEqual(report["first_body_entry"]["ego"]["frame"], 11)
            self.assertEqual(report["first_body_entry"]["other"]["frame"], 12)
            self.assertAlmostEqual(report["ego_minus_other_entry_time_s"], -.05)
            self.assertEqual(report["geometric_yield_candidate"], "other")
            self.assertTrue(report["ego_is_to_other_right"])
            self.assertIn("unresolved", report["approximately_same_time_judgment"])

    def test_right_hand_approach_reverses_geometric_candidate(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            write_sources(root)
            context = json.loads((root / "road_geometry.json").read_text())
            context["other_approach_origin_xy_m"] = [0, -8]
            context["other_approach_heading_deg"] = 90
            (root / "road_geometry.json").write_text(json.dumps(context))
            report = MODULE.analyze(root)
            self.assertEqual(report["geometric_yield_candidate"], "ego")
            self.assertTrue(report["other_is_to_ego_right"])

    def test_rejects_ambiguous_or_nonreciprocal_approach(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            write_sources(root)
            context = json.loads((root / "road_geometry.json").read_text())
            context["other_approach_origin_xy_m"] = [-6, 0]
            (root / "road_geometry.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "geometrically ambiguous"):
                MODULE.analyze(root)

    def test_rejects_missing_road_context(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            write_sources(root)
            context = json.loads((root / "road_geometry.json").read_text())
            del context["device_inventory_source"]
            (root / "road_geometry.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "Missing sourced road context"):
                MODULE.analyze(root)

    def test_rejects_frame_mismatch(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            write_sources(root)
            frames = [json.loads(x) for x in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[2]["carla_frame"] = 99
            (root / "video_frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in frames))
            with self.assertRaisesRegex(ValueError, "Original frame/time join failed"):
                MODULE.analyze(root)


if __name__ == "__main__":
    unittest.main()
