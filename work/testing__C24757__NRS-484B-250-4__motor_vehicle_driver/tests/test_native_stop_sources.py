import importlib.util
import types
import unittest
import json
import tempfile
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "native_stop_sources", Path(__file__).resolve().parents[1] / "native_stop_sources.py")
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)
measurement_spec = importlib.util.spec_from_file_location(
    "inoperative_stop_measurements", Path(__file__).resolve().parents[1] / "inoperative_stop_measurements.py")
measure = importlib.util.module_from_spec(measurement_spec)
measurement_spec.loader.exec_module(measure)


class Actor:
    def __init__(self, x, speed):
        self.x, self.speed = x, speed
        self.bounding_box = types.SimpleNamespace(get_world_vertices=self.vertices)

    def get_transform(self):
        return None

    def vertices(self, transform):
        return [types.SimpleNamespace(x=self.x + dx, y=dy)
                for dx, dy in [(0, -1), (0, 1), (-2, -1), (-2, 1)]]

    def get_velocity(self):
        return types.SimpleNamespace(x=self.speed, y=0, z=0)


class SourceTests(unittest.TestCase):
    def site(self, kind):
        return {"intersection_id": 6, "native_signal_id": 13,
                "stop_boundary": {"kind": kind, "source": "reviewed-map-and-original-video",
                                  "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]},
                "other_stop_boundary": {"kind": kind, "source": "other-approach-map-and-video",
                                        "point_xy_m": [0, 0], "upstream_normal_xy": [-1, 0]}}

    def test_body_front_signed_distance_and_original_off_readback(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        for kind, field in [("stop_line", "front_to_stop_line_signed_m"),
                            ("crosswalk", "front_to_crosswalk_signed_m"),
                            ("nearest_view", "front_to_nearest_view_signed_m")]:
            row = sources.source_row(100, 1.0, signal, Actor(-3, 0), Actor(-5, 2), self.site(kind))
            self.assertEqual(row["ego"][field], 3)
            self.assertEqual(row["other"][field], 5)
            self.assertEqual(row["signal_state"], "Off")
            self.assertEqual(len(row["ego"]["body_vertices_xy_m"]), 4)

    def test_other_approach_uses_its_own_boundary_geometry(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        site = self.site("stop_line")
        site["other_stop_boundary"]["point_xy_m"] = [0, -5]
        site["other_stop_boundary"]["upstream_normal_xy"] = [0, 1]
        row = sources.source_row(100, 1.0, signal, Actor(-3, 0), Actor(-5, 0), site)
        self.assertEqual(row["ego"]["front_to_stop_line_signed_m"], 3)
        self.assertEqual(row["other"]["front_to_stop_line_signed_m"], 4)

    def test_rejects_unreviewed_geometry_and_operating_head(self):
        site = self.site("stop_line")
        site["stop_boundary"]["source"] = ""
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        with self.assertRaisesRegex(ValueError, "Sourced statutory stop boundary"):
            sources.source_row(100, 1, signal, Actor(-3, 0), Actor(-5, 2), site)
        site = self.site("stop_line")
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Green")
        with self.assertRaisesRegex(ValueError, "Off readback"):
            sources.source_row(100, 1, signal, Actor(-3, 0), Actor(-5, 2), site)

    def test_native_source_rows_feed_saved_measurement(self):
        signal = types.SimpleNamespace(id=13, get_state=lambda: "Off")
        site = self.site("stop_line")
        context = {"native_map_id": "TownX", "intersection_id": 6,
                   "native_signal_id": 13, "signal_head_video_source": "front-original",
                   "lane_governance_source": "native-affected-waypoints",
                   "stop_line_source": "reviewed-map-and-original-video",
                   "other_stop_boundary": {"kind": "stop_line", "source": "other-approach-map-and-video"},
                   "installed_uncovered_vehicular_heads": True,
                   "stop_line_exists": True,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        ego = [Actor(-3, 2), Actor(-3, 2), Actor(-3, 0), Actor(1, 2)]
        other = [Actor(-3, 2), Actor(-3, 0), Actor(1, 2), Actor(3, 2)]
        rows = [sources.source_row(100 + i, 1 + i * .05, signal, ego[i], other[i], site)
                for i in range(4)]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "junction_context.json").write_text(json.dumps(context))
            (root / "vehicle_signal_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            report = measure.analyze(root)
        self.assertTrue(report["other_completed_stop_before_ego_observed"])
        self.assertTrue(report["other_body_inside_at_ego_entry_observed"])


if __name__ == "__main__":
    unittest.main()
