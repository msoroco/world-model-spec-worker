import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from road_source_capture import RoadSourceRecorder, sample_two_way_baseline
from right_half_measurement import measure
from right_half_route import baseline_targets, control_step, select_two_way_route


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Transform:
    def __init__(self, x, y, direction):
        self.location = Point(x, y)
        self.direction = direction

    def get_forward_vector(self):
        return Point(*self.direction)


class Waypoint:
    lane_type = "Driving"
    lane_width = 4.0
    road_id = 7
    is_junction = False

    def __init__(self, y, direction, lane_id):
        self.transform = Transform(0, y, direction)
        self.lane_id = lane_id
        self.other = None

    def get_left_lane(self):
        return self.other

    def get_right_lane(self):
        return None

    def next(self, spacing_m):
        return [self.following] if getattr(self, "following", None) else []


class Box:
    def __init__(self, y):
        self.y = y

    def get_world_vertices(self, transform):
        return [Point(x, self.y + dy, z)
                for z in (0, 1.5) for x, dy in
                ((-1, -0.6), (1, -0.6), (1, 0.6), (-1, 0.6))]


class Actor:
    def __init__(self, y):
        self.bounding_box = Box(y)

    def get_transform(self):
        return object()


def pair(direction):
    east = Waypoint(-2, (1, 0), -1)
    west = Waypoint(2, (-1, 0), 1)
    east.other, west.other = west, east
    return east if direction == "east" else west


class RoadSourceCaptureTest(unittest.TestCase):
    def test_original_body_and_direction_join_measurement(self):
        for direction, body_y in (("east", -2), ("west", 2)):
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                waypoint = pair(direction)
                rows = [sample_two_way_baseline(Actor(body_y), waypoint, frame,
                                                frame / 20) for frame in range(2)]
                (root / "ego_road_frames.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows))
                (root / "road_exception_context.json").write_text(json.dumps({
                    key: {"value": None, "source_ref": None} for key in
                    ("passing_same_direction", "right_half_closed", "three_lane_highway",
                     "posted_one_way", "insufficient_width")}) + "\n")
                observed = measure(root / "ego_road_frames.jsonl",
                                   root / "road_exception_context.json")
                self.assertTrue(all(row["whole_body_right_half"]
                                    for row in observed["observations"]))
                self.assertEqual(rows[0]["road_width_m"], 8)

    def test_missing_opposing_and_bad_centerline_rejected(self):
        waypoint = pair("east")
        waypoint.other = None
        with self.assertRaisesRegex(ValueError, "opposing driving lane"):
            sample_two_way_baseline(Actor(-2), waypoint, 0, 0)
        waypoint = pair("east")
        waypoint.other.transform.location.y = 8
        with self.assertRaisesRegex(ValueError, "centerline"):
            sample_two_way_baseline(Actor(-2), waypoint, 0, 0)

    def test_route_and_both_body_side_targets(self):
        class Map:
            def __init__(self):
                self.route = []
                for index in range(17):
                    east = Waypoint(-2, (1, 0), -1)
                    west = Waypoint(2, (-1, 0), 1)
                    east.transform.location.x = index * 2.5
                    west.transform.location.x = index * 2.5
                    east.other, west.other = west, east
                    if self.route:
                        self.route[-1].following = east
                    self.route.append(east)

            def get_spawn_points(self):
                return [self.route[0].transform]

            def get_waypoint(self, location):
                return self.route[0]

        route = select_two_way_route(Map())
        right, left = (baseline_targets(route, body_side=side)
                       for side in ("right", "left"))
        self.assertEqual(len(right["targets_xy_m"]), 17)
        self.assertTrue(all(y == -2 for _, y in right["targets_xy_m"]))
        self.assertTrue(all(y == 2 for _, y in left["targets_xy_m"]))
        self.assertEqual(right["other_vehicle_start_xy_m"], [20, -2])
        self.assertGreater(control_step((0, -2), (1, 0), (0, 0), (2.5, -2))["throttle"], 0)
        route[8].other = None
        with self.assertRaisesRegex(ValueError, "opposing driving lane"):
            baseline_targets(route, body_side="left")

    def test_original_recorder_keeps_sequence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            recorder = RoadSourceRecorder(temporary)
            waypoint = pair("east")
            recorder.append(Actor(-2), waypoint, 21, 0)
            with self.assertRaisesRegex(ValueError, "consecutive"):
                recorder.append(Actor(-2), waypoint, 23, .1)
            recorder.append(Actor(-2), waypoint, 22, .05)
            recorder.close()
            with self.assertRaisesRegex(ValueError, "closed"):
                recorder.append(Actor(-2), waypoint, 23, .1)
            with self.assertRaises(FileExistsError):
                RoadSourceRecorder(temporary)
            rows = [json.loads(line) for line in
                    (Path(temporary) / "ego_road_frames.jsonl").read_text().splitlines()]
            self.assertEqual([row["frame"] for row in rows], [21, 22])


if __name__ == "__main__":
    unittest.main()
