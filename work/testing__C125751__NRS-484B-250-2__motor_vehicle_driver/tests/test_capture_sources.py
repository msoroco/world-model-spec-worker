import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE.parents[1] / "runtime/scenario_pipeline"))
from capture_sources import record_frame, source_contexts
from entry_measurements import analyze as measure_entry
from signal_measurements import analyze as measure_signal
from stop_measurements import analyze as measure_stop
from worker_exchange.native_output import FrameMap


def actor(identity, x, y, yaw, speed):
    pose = NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))
    box = NS(get_world_vertices=lambda _: [NS(x=x+dx, y=y+dy) for dx, dy in
                                           ((-.3,-.3),(.3,-.3),(.3,.3),(-.3,.3))])
    velocity = NS(x=speed if yaw == 0 else 0, y=speed if yaw == 90 else 0, z=0)
    return NS(id=identity, bounding_box=box, get_transform=lambda: pose,
              get_location=lambda: pose.location, get_velocity=lambda: velocity)


def plan():
    return {"physical_acceptance_claimed": False, "native_junction_id": 7,
            "crossing_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
            "crossing_polygon_source": "test Native junction polygon",
            "ego_highway_id": 1, "other_highway_id": 2,
            "approaches": {"ego": {"start_xy_m": [-8,0], "heading_deg": 0,
                                   "road_id": 11, "lane_id": -1},
                           "other": {"start_xy_m": [0,-8], "heading_deg": 90,
                                     "road_id": 22, "lane_id": -1}}}


def site():
    return {"native_map_name": "FixtureTown",
            "device_inventory_source": "test Native light inventory",
            "approach_geometry_source": "test Native waypoints",
            "routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                       "other": [[0,-10],[0,-4],[0,0],[0,10]]},
            "selected_stop_references": {
                "ego": {"kind": "marked_stop_line", "segment_xy_m": [[-5,-2],[-5,2]],
                        "geometry_source": "test Native ego marking", "reference_review_source": "test ego review"},
                "other": {"kind": "marked_stop_line", "segment_xy_m": [[-2,-5],[2,-5]],
                          "geometry_source": "test Native other marking", "reference_review_source": "test other review"}}}


def world_map():
    def waypoint(loc, project_to_road=False):
        road = 11 if loc.y == 0 else 22
        inside = -5 <= loc.x <= 5 and -5 <= loc.y <= 5
        return NS(road_id=road, lane_id=-1, is_junction=inside,
                  get_junction=lambda: NS(id=7))
    return NS(get_waypoint=waypoint)


class CaptureSourceTests(unittest.TestCase):
    def test_native_rows_feed_all_saved_measurements(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            light = NS(id=55, get_state=lambda: "Off")
            other_light = NS(id=56, get_state=lambda: "Off")
            for name, value in source_contexts(site(), plan(), light, other_light).items():
                (root / name).write_text(json.dumps(value) + "\n")
            (root / "approach.mkv").write_bytes(b"fake source for hash join only")
            with FrameMap(root / "video_frames.jsonl") as frames, \
                 (root / "crossing_history.jsonl").open("x") as crossing, \
                 (root / "signal_history.jsonl").open("x") as signal, \
                 (root / "stop_history.jsonl").open("x") as stop:
                for i, (ex, oy, es, os) in enumerate(((-8,-8,0,0),(-4,-8,2,0),(-4,-4,2,2))):
                    snap = NS(frame=100+i, timestamp=NS(elapsed_seconds=.05*i))
                    mapped, c, s, st = record_frame(frames, crossing, signal, stop,
                        snap, world_map(), actor(1,ex,0,0,es), actor(2,0,oy,90,os),
                        light, other_light, plan(), "Off", "Off")
                    self.assertEqual(mapped["video_frame"], i)
                    self.assertEqual(s["native_signal_id"], 55)
                    if i == 2:
                        self.assertGreater(st["other"]["front_xy_m"][1], oy)
            review = {"camera": "approach", "video_frame": 1, "carla_frame": 101,
                      "native_signal_id": 55,
                      "source_video_sha256": hashlib.sha256((root / "approach.mkv").read_bytes()).hexdigest(),
                      "head_region_px": [1,1,3,3], "installed": True, "uncovered": True,
                      "review_basis": "fake source join only; no physical pixel claim"}
            (root / "head_visibility_review.json").write_text(json.dumps(review))
            other_review = {**review, "native_signal_id": 56}
            (root / "other_head_visibility_review.json").write_text(json.dumps(other_review))
            entry = measure_entry(root)
            self.assertEqual(entry["first_body_entry"]["ego"]["frame"], 101)
            self.assertEqual(entry["first_body_entry"]["other"]["frame"], 102)
            self.assertEqual(measure_signal(root, entry)["at_body_entry"]["ego"]["native_state"], "Off")
            self.assertFalse(measure_stop(root, entry)["other_body_inside_at_ego_entry"])

    def test_state_drift_rejected_before_frame_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            light = NS(id=55, get_state=lambda: "Red")
            other_light = NS(id=56, get_state=lambda: "Off")
            with FrameMap(root / "video_frames.jsonl") as frames:
                with self.assertRaisesRegex(ValueError, "state drift"):
                    record_frame(frames, io.StringIO(), io.StringIO(), io.StringIO(),
                        NS(frame=1, timestamp=NS(elapsed_seconds=0)), world_map(),
                        actor(1,-8,0,0,0), actor(2,0,-8,90,0), light, other_light,
                        plan(), "Off", "Off")
            self.assertEqual((root / "video_frames.jsonl").read_text(), "")

    def test_context_requires_sourced_reference(self):
        bad = site()
        del bad["selected_stop_references"]["other"]["reference_review_source"]
        with self.assertRaisesRegex(ValueError, "provenance required: other"):
            source_contexts(bad, plan(), NS(id=55), NS(id=56))


if __name__ == "__main__":
    unittest.main()
