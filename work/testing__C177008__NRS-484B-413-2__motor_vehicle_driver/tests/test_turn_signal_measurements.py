import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from xml.etree import ElementTree as ET


spec = importlib.util.spec_from_file_location("turn_signal_measurements", Path(__file__).resolve().parents[1] / "turn_signal_measurements.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class TurnSignalTests(unittest.TestCase):
    def test_generated_right_turn_road_projects_with_pinned_adapter(self):
        import sys
        runtime = next((parent / "runtime" / "scenario_pipeline"
                        for parent in Path(__file__).resolve().parents
                        if (parent / "runtime" / "scenario_pipeline").is_dir()), None)
        if runtime is None:
            self.fail("Pinned runtime/scenario_pipeline unavailable")
        sys.path.insert(0, str(runtime))
        from traffic_spec_adapter.geometry import static_map
        xml = measure.build_right_turn_opendrive()
        tree = ET.fromstring(xml)
        roads = {int(road.attrib["id"]): road for road in tree.findall("road")}
        self.assertEqual(set(roads), {177008, 177010, 177011})
        self.assertEqual(float(roads[177008].attrib["length"]), 120.0)
        self.assertEqual(float(roads[177010].find("planView/geometry/arc").attrib["curvature"]), -0.1)
        self.assertEqual(tree.find("junction/connection/laneLink").attrib, {"from":"-1", "to":"-1"})
        self.assertNotIn("business", xml.lower())
        road = Path(__file__).resolve().parents[1] / "native-map-plan" / "right-turn-approach.xodr"
        self.assertEqual(road.read_text(), xml)
        regions, _, lane_ids = static_map(road, junctions=True)
        self.assertEqual(set(lane_ids), {(177008, 0, -1), (177010, 0, -1), (177011, 0, -1)})
        self.assertTrue(any(item["kind"] == "intersection" for item in regions))

    @staticmethod
    def waypoint(x, y, road=1, lane=-1):
        return NS(road_id=road, lane_id=lane,
                  transform=NS(location=NS(x=x, y=y)))

    def test_native_right_turn_spawn_and_cleanup(self):
        approach = [self.waypoint(x, 0) for x in range(0, 101, 2)]
        departure = [self.waypoint(100, -2, 2), self.waypoint(100, -4, 2)]
        destroyed = []
        vehicle = NS(get_location=lambda: approach[0].transform.location,
                     destroy=lambda: destroyed.append(True))
        world = NS(try_spawn_actor=lambda blueprint, transform: vehicle,
                   get_map=lambda: NS(get_waypoint=lambda location, project_to_road: approach[0]))
        with measure.spawn_native_right_turn(world, "vehicle", approach, departure) as built:
            self.assertEqual(built["route"]["direct_approach_m"], 100)
            self.assertAlmostEqual(built["route"]["turn_angle_deg"], -90)
        self.assertEqual(destroyed, [True])

    def test_native_route_rejects_lane_change_short_approach_and_left_turn(self):
        long = [self.waypoint(x, 0) for x in range(0, 101, 2)]
        right = [self.waypoint(100, -2, 2), self.waypoint(100, -4, 2)]
        with self.assertRaisesRegex(ValueError, "shorter"):
            measure.verify_native_right_turn(long[:25], right)
        with self.assertRaisesRegex(ValueError, "lane or road changes"):
            measure.verify_native_right_turn(long[:-1] + [self.waypoint(100, 0, lane=-2)], right)
        left = [self.waypoint(100, 2, 2), self.waypoint(100, 4, 2)]
        with self.assertRaisesRegex(ValueError, "not a right turn"):
            measure.verify_native_right_turn(long, left)
        with self.assertRaisesRegex(ValueError, "distinct outgoing road"):
            measure.verify_native_right_turn(long, [self.waypoint(100, -2), self.waypoint(100, -4)])

    def test_native_indicator_readback_preserves_lamps_and_rejects_failure(self):
        class State:
            RightBlinker = 8
        class Vehicle:
            lights = 1
            def get_light_state(self):
                return self.lights
            def set_light_state(self, value):
                self.lights = value
        vehicle = Vehicle()
        self.assertTrue(measure.set_native_right_blinker(vehicle, State, True)["readback_right_indicator"])
        self.assertEqual(vehicle.lights, 9)
        self.assertFalse(measure.set_native_right_blinker(vehicle, State, False)["readback_right_indicator"])
        self.assertEqual(vehicle.lights, 1)
        vehicle.set_light_state = lambda value: None
        with self.assertRaisesRegex(ValueError, "readback"):
            measure.set_native_right_blinker(vehicle, State, True)

    def test_route_distance_indicator_schedule_and_interruption(self):
        request = measure.indicator_request_at_remaining_distance
        self.assertFalse(request(30.49, start_m=30.48))
        self.assertTrue(request(30.48, start_m=30.48))
        self.assertTrue(request(0, start_m=30.48))
        self.assertFalse(request(91.45, start_m=91.44))
        self.assertTrue(request(91.44, start_m=91.44))
        self.assertFalse(request(10, start_m=30.48, interruption_m=(9, 11)))
        self.assertTrue(request(8.9, start_m=30.48, interruption_m=(9, 11)))
        with self.assertRaisesRegex(ValueError, "inside the active approach"):
            request(20, start_m=30.48, interruption_m=(10, 40))

    def test_selected_native_lane_chain_and_controller_uses_actual_pose(self):
        def waypoint(road, lane, station):
            if road == 177008:
                x, y = station - 120, -1.8
            else:
                angle = station / 10
                x, y = 1.8 + 10 * math.sin(angle), -10 * (1 - math.cos(angle)) - 1.8
            return NS(road_id=road, lane_id=lane, s=station,
                      transform=NS(location=NS(x=x, y=y)))
        native_map = NS(get_waypoint_xodr=waypoint)
        route = measure.select_native_route(native_map)
        self.assertEqual(route["approach_road_id"], 177008)
        self.assertEqual(route["outgoing_road_id"], 177010)
        self.assertGreaterEqual(route["direct_approach_m"], 91.44)
        pose = NS(location=NS(x=-50, y=-1.8), rotation=NS(yaw=0))
        vehicle = NS(get_transform=lambda: pose,
                     get_velocity=lambda: NS(x=4.0, y=0.0, z=0.0))
        command = measure.native_route_control(vehicle, route)
        self.assertAlmostEqual(command["remaining_approach_m"], 50)
        self.assertGreater(command["throttle"], 0)
        self.assertEqual(command["brake"], 0)
        self.assertAlmostEqual(command["steer"], 0, places=2)
        self.assertFalse(measure.indicator_request_at_remaining_distance(
            command["remaining_approach_m"], start_m=30.48))
        pose.location.x = -30
        self.assertTrue(measure.indicator_request_at_remaining_distance(
            measure.native_route_control(vehicle, route)["remaining_approach_m"], start_m=30.48))
        missing = NS(get_waypoint_xodr=lambda road, lane, station: None)
        with self.assertRaisesRegex(ValueError, "station missing"):
            measure.select_native_route(missing)

    def fixture(self, root, distance, district="business", interrupted=False):
        steps = math.ceil(distance / 0.25)
        step = distance / steps
        context = {"native_map_id": "TownX", "approach_road_id": 1,
                   "approach_lane_id": -1, "outgoing_road_id": 2,
                   "outgoing_lane_id": -1, "native_route_source": "native-lane-links",
                   "district_source": "source-reviewed-map-context",
                   "district_type": district, "turn_onset_frame": 101 + steps}
        (root / "route_context.json").write_text(json.dumps(context))
        rows = []
        for i in range(steps + 2):
            point = [step * (i - 1), 0]
            if i == steps + 1:
                point = [distance - step + step * math.cos(math.pi / 6),
                         -step * math.sin(math.pi / 6)]
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "ego_position_xy_m": point, "ego_speed_mps": step / .05,
                         "ego_heading_deg": -30 if i == steps + 1 else 0,
                         "right_indicator": i > 0 and not (interrupted and i == steps // 2)})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "drive_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_100_foot_below_at_above_and_300_foot_area(self):
        for distance, expected in ((30.47, False), (30.48, True), (30.49, True)):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, distance)
                result = measure.analyze(root)
                self.assertAlmostEqual(result["turn_onset"]["continuous_right_signal_distance_m"], distance)
                self.assertEqual(result["turn_onset"]["heading_delta_deg"], -30)
                self.assertEqual(result["observed_continuous_distance_meets_boundary"], expected)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, district="other")
            self.assertAlmostEqual(measure.analyze(root)["required_distance_m"], 91.44)

    def test_interruption_resets_distance_and_stale_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48, interrupted=True)
            result = measure.analyze(root)
            self.assertLess(result["turn_onset"]["continuous_right_signal_distance_m"], 30.48)
            self.fixture(root, 30.48)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[3]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_turn_onset_must_match_source_heading_and_turn_right(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48)
            path = root / "drive_history.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[-1]["ego_heading_deg"] = 0
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "heading disagrees"):
                measure.analyze(root)
            rows[-1]["ego_heading_deg"] = 30
            rows[-1]["ego_position_xy_m"][1] *= -1
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not a right turn"):
                measure.analyze(root)
            rows[-1]["ego_heading_deg"] = -30
            rows[-1]["ego_position_xy_m"][1] *= -1
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            context = json.loads((root / "route_context.json").read_text())
            context["turn_onset_frame"] -= 1
            (root / "route_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "Authored turn onset"):
                measure.analyze(root)

    def test_path_jump_incompatible_with_speed_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 30.48)
            path = root / "drive_history.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[5]["ego_position_xy_m"][0] += 10
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "path jump exceeds source speed"):
                measure.analyze(root)


if __name__ == "__main__":
    unittest.main()
