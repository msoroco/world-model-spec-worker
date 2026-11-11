import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))
from capture_sources import record_crossing_sample, road_geometry
from camera_setup import source_cameras
from entry_measurements import analyze
from worker_exchange.native_output import FrameMap


def actor(identity, x, y):
    pose = NS(location=NS(x=x, y=y), rotation=NS(yaw=0))
    box = NS(get_world_vertices=lambda _: [NS(x=x+dx, y=y+dy) for dx, dy in
                                           ((-.3,-.3),(.3,-.3),(.3,.3),(-.3,.3))])
    return NS(id=identity, bounding_box=box, get_transform=lambda: pose,
              get_location=lambda: pose.location,
              get_velocity=lambda: NS(x=1, y=0, z=0))


class CaptureTests(unittest.TestCase):
    def test_original_frame_capture_feeds_entry_analysis(self):
        plan = {"physical_acceptance_claimed": False, "native_junction_id": 7,
                "crossing_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
                "crossing_polygon_source": "synthetic test polygon",
                "approach_geometry_source": "synthetic test waypoints",
                "ego_highway_id": 1, "other_highway_id": 2,
                "approaches": {"ego": {"start_xy_m": [-8,0], "heading_deg": 0},
                               "other": {"start_xy_m": [0,-8], "heading_deg": 90}}}
        waypoint = NS(road_id=33, lane_id=-1, is_junction=True,
                      get_junction=lambda: NS(id=7))
        world_map = NS(get_waypoint=lambda loc, project_to_road=False: waypoint)
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "road_geometry.json").write_text(json.dumps(road_geometry(
                {"device_inventory_source": "synthetic test inventory",
                 "device_review": {"official_device_controls_crossing": False}}, plan)))
            with FrameMap(root / "video_frames.jsonl") as frames, (root / "crossing_history.jsonl").open("x") as history:
                for i, (ex, oy) in enumerate(((-8,-8),(-4,-8),(-4,-4))):
                    snap = NS(frame=10+i, timestamp=NS(elapsed_seconds=.5+i*.05))
                    mapping, row = record_crossing_sample(frames, history, snap,
                                    world_map, actor(1, ex, 0), actor(2, 0, oy), plan)
                    self.assertEqual(mapping["video_frame"], i)
                    self.assertEqual(row["ego"]["native_junction_id"], 7)
            report = analyze(root)
            self.assertEqual(report["first_body_entry"]["ego"]["frame"], 11)
            self.assertEqual(report["first_body_entry"]["other"]["frame"], 12)
            self.assertTrue(report["other_is_to_ego_right"])

    def test_requires_reviewed_device_source(self):
        with self.assertRaisesRegex(ValueError, "device inventory"):
            road_geometry({}, {"approaches": {}})
        with self.assertRaisesRegex(ValueError, "uncontrolled crossing"):
            road_geometry({"device_inventory_source": "test",
                           "device_review": {"official_device_controls_crossing": True}},
                          {"approaches": {}})

    def test_four_cameras_created_and_cleaned(self):
        calls = []
        class Blueprint:
            def set_attribute(self, name, value):
                calls.append((name, value))
        def spawn(blueprint, transform, **kwargs):
            sensor = NS(stop=lambda: calls.append("stop"),
                        destroy=lambda: calls.append("destroy"))
            calls.append(("spawn", kwargs))
            return sensor
        world = NS(get_blueprint_library=lambda: NS(find=lambda _: Blueprint()),
                   spawn_actor=spawn)
        transforms = {name: object() for name in
                      ("overview", "approach", "reference_corner", "driver_reference")}
        with source_cameras(world, object(), transforms) as sensors:
            self.assertEqual(set(sensors), set(transforms))
        self.assertEqual(calls.count("stop"), 4)
        self.assertEqual(calls.count("destroy"), 4)
        self.assertEqual(len([c for c in calls if isinstance(c, tuple) and c[0] == "spawn"]), 4)


if __name__ == "__main__":
    unittest.main()
