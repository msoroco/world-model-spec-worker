import importlib.util
import json
import tempfile
import unittest
import turn_context
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opposite_turn_construction", HERE / "opposite_turn_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runner_spec = importlib.util.spec_from_file_location("opposite_turn_runner", HERE / "opposite_turn_runner.py")
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)


def site():
    return {"routes": {"ego": [[-10, 0], [-5, 0], [0, 0], [0, 5]],
                       "other": [[10, 0], [5, 0], [0, 0], [-5, 0]]},
            "expected_approach_lanes": {"ego": [11, -1], "other": [11, 1]}}


class Actor:
    def __init__(self, lane, yaw):
        self.lane, self.yaw, self.destroyed = lane, yaw, False
        self.id = id(self)
        self.bounding_box = SimpleNamespace(get_world_vertices=self.body_vertices)

    def body_vertices(self, pose):
        x, y = pose.location.x, pose.location.y
        return [SimpleNamespace(x=x+dx, y=y+dy)
                for dx, dy in ((-2, -1), (-2, 1), (2, -1), (2, 1))]

    def get_location(self):
        return self

    def get_transform(self):
        x = -10 if self.yaw == 0 else 10
        return SimpleNamespace(location=SimpleNamespace(x=x, y=0),
                               rotation=SimpleNamespace(yaw=self.yaw))

    def get_velocity(self):
        return SimpleNamespace(x=0., y=0., z=0.)

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, actors):
        self.actors = actors
        self.index = 0
        self.ticks = 0

    def try_spawn_actor(self, blueprint, transform):
        actor = self.actors[self.index]
        self.index += 1
        return actor

    def tick(self):
        self.ticks += 1
        return self.ticks

    def get_map(self):
        return self

    def get_waypoint(self, actor, project_to_road):
        return SimpleNamespace(road_id=actor.lane[0], lane_id=actor.lane[1],
                               is_junction=False)


class OppositeTurnConstructionTest(unittest.TestCase):
    def test_opposing_left_turn_spawns_and_releases(self):
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        world = World(actors)
        with module.construct_opposite_turn_pair(world, {"ego": "car", "other": "car"},
                                                 {"ego": "pose1", "other": "pose2"}, site(), "ego") as built:
            self.assertEqual(built["geometry"]["approach_separation_deg"], 180)
            self.assertFalse(built["legal_exception_verified"])
            self.assertEqual(world.ticks, 1)
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_rejects_perpendicular_and_nonleft_routes(self):
        changed = site()
        changed["routes"]["other"] = [[0, -10], [0, -5], [0, 0], [0, 5]]
        with self.assertRaisesRegex(ValueError, "geometrically opposite"):
            module.check_routes(changed["routes"], "ego")
        changed = site()
        changed["routes"]["ego"] = [[-10, 0], [-5, 0], [0, 0], [5, 0]]
        with self.assertRaisesRegex(ValueError, "geometric left"):
            module.check_routes(changed["routes"], "ego")

    def test_rejects_wrong_native_lane_and_cleans_up(self):
        actors = [Actor([11, -1], 0), Actor([12, 1], 180)]
        with self.assertRaisesRegex(ValueError, "outside sourced approach lane"):
            with module.construct_opposite_turn_pair(World(actors), {"ego": "car", "other": "car"},
                                                     {"ego": "pose1", "other": "pose2"}, site(), "ego"):
                pass
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_route_commands_hold_then_release_both_roles(self):
        actors = {"ego": Actor([11, -1], 0), "other": Actor([11, 1], 180)}
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        progress = {"ego": 1, "other": 1}
        before = module.command_opposite_turn_pair(
            carla, actors, site(), progress, 7, {"ego": 8, "other": 10},
            {"ego": 5., "other": 5.}, "ego")
        self.assertFalse(before["decisions"]["ego"]["release_allowed"])
        self.assertEqual(actors["ego"].control.brake, 1.)
        self.assertEqual(actors["other"].control.brake, 1.)
        ego_release = module.command_opposite_turn_pair(
            carla, actors, site(), progress, 8, {"ego": 8, "other": 10},
            {"ego": 5., "other": 5.}, "ego")
        self.assertGreater(actors["ego"].control.throttle, 0.)
        self.assertEqual(actors["other"].control.brake, 1.)
        self.assertFalse(ego_release["legal_exception_verified"])
        module.command_opposite_turn_pair(
            carla, actors, site(), progress, 10, {"ego": 8, "other": 10},
            {"ego": 5., "other": 5.}, "ego")
        self.assertGreater(actors["other"].control.throttle, 0.)

    def test_bad_route_index_applies_no_partial_command(self):
        actors = {"ego": Actor([11, -1], 0), "other": Actor([11, 1], 180)}
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        with self.assertRaisesRegex(ValueError, 'route target index'):
            module.command_opposite_turn_pair(
                carla, actors, site(), {"ego": 1, "other": 0}, 8,
                {"ego": 8, "other": 10}, {"ego": 5., "other": 5.}, "ego")
        self.assertFalse(hasattr(actors["ego"], "control"))
        self.assertFalse(hasattr(actors["other"], "control"))

    def test_other_driver_can_be_the_left_turner(self):
        changed = site()
        changed["routes"]["ego"] = [[-10, 0], [-5, 0], [0, 0], [5, 0]]
        changed["routes"]["other"] = [[10, 0], [5, 0], [0, 0], [0, -5]]
        actors = {"ego": Actor([11, -1], 0), "other": Actor([11, 1], 180)}
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        result = module.command_opposite_turn_pair(
            carla, actors, changed, {"ego": 1, "other": 3}, 10,
            {"ego": 8, "other": 10}, {"ego": 5., "other": 5.}, "other")
        self.assertEqual(result["turning_role"], "other")
        self.assertAlmostEqual(result["geometry"]["routes"]["other"]["deflection_deg"], 90.)
        self.assertGreater(actors["other"].control.throttle, 0.)
        self.assertLess(actors["other"].control.steer, 0.)

    def test_candidate_runner_records_original_frames_and_four_camera_joins(self):
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        world = World(actors)
        records = []
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        receipt = runner.run_candidate_opposite_turn(
            world, carla, site(), "ego", {"ego": "car", "other": "car"},
            {"ego": "pose1", "other": "pose2"},
            {"ego": 1, "other": 2}, {"ego": 5., "other": 5.}, 3,
            lambda frame: {name: frame for name in
                           ("overview", "approach", "reference_corner", "driver_reference")},
            records.append)
        self.assertEqual([record["native_frame"] for record in records], [2, 3, 4])
        self.assertEqual(receipt["frames_recorded"], 3)
        self.assertEqual(records[0]["actor_sources"]["ego"]["position_xy_m"], [-10., 0.])
        self.assertEqual(len(records[0]["actor_sources"]["ego"]["body_vertices_xy_m"]), 4)
        self.assertFalse(records[0]["physical_or_legal_acceptance_claimed"])
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_candidate_runner_rejects_camera_mismatch_and_cleans_up(self):
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        with self.assertRaisesRegex(ValueError, "All four camera sources"):
            runner.run_candidate_opposite_turn(
                World(actors), carla, site(), "ego",
                {"ego": "car", "other": "car"},
                {"ego": "pose1", "other": "pose2"},
                {"ego": 1, "other": 2}, {"ego": 5., "other": 5.}, 1,
                lambda frame: {"overview": frame}, lambda record: None)
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_candidate_media_writes_four_streams_and_original_source_records(self):
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        world = World(actors)
        sensors = {}
        written = {}

        class Sensor:
            def listen(self, callback):
                self.callback = callback

        original_tick = world.tick

        def tick():
            frame = original_tick()
            for sensor in sensors.values():
                sensor.callback(SimpleNamespace(frame=frame, raw_data=b"BGRA"))
            return frame

        world.tick = tick
        world.get_snapshot = lambda: SimpleNamespace(
            frame=world.ticks,
            timestamp=SimpleNamespace(elapsed_seconds=world.ticks * .05))

        @contextmanager
        def cameras(active_world, ego, poses):
            self.assertIs(active_world, world)
            self.assertIs(ego, actors[0])
            sensors.update({name: Sensor() for name in poses})
            yield sensors

        class Writer:
            def __init__(self, path, width, height):
                written[path.name] = []
                self.name = path.name

            def __enter__(self):
                return self

            def write(self, data):
                written[self.name].append(data)

            def __exit__(self, *args):
                return None

        carla = SimpleNamespace(
            VehicleControl=lambda: SimpleNamespace(),
            Location=lambda **kwargs: kwargs,
            Rotation=lambda **kwargs: kwargs,
            Transform=lambda location, rotation: (location, rotation))
        value = dict(site(), cameras={name: [0, 0, 10, 0, 0, 0] for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")},
                     crossing_polygon_xy_m=[[-3, -3], [3, -3], [3, 3], [-3, 3]],
                     crossing_polygon_source="synthetic fake-Native test polygon",
                     native_junction_id=77,
                     approach_headings_deg={"ego": 0, "other": 180},
                     approach_geometry_source="synthetic fake-Native test route",
                     governed_signal_ids={"ego": 101, "other": 102},
                     device_inventory_source="synthetic fake-Native signal inventory")
        lights = {"ego": SimpleNamespace(id=101, get_state=lambda: "Green"),
                  "other": SimpleNamespace(id=102, get_state=lambda: "Red")}
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(runner, "source_cameras", cameras), patch.object(runner, "FFV1Writer", Writer):
                receipt = runner.capture_candidate_media(
                    Path(temp), world, carla, value, "ego",
                    {"ego": "car", "other": "car"},
                    {"ego": "pose1", "other": "pose2"},
                    {"ego": 1, "other": 2}, {"ego": 5., "other": 5.}, 3,
                    governed_lights=lights)
            source = [json.loads(line) for line in
                      (Path(temp) / "body_history.jsonl").read_text().splitlines()]
            frames = [json.loads(line) for line in
                      (Path(temp) / "video_frames.jsonl").read_text().splitlines()]
            crossings = [json.loads(line) for line in
                         (Path(temp) / "crossing_history.jsonl").read_text().splitlines()]
            stops = [json.loads(line) for line in
                     (Path(temp) / "stop_history.jsonl").read_text().splitlines()]
            signals = [json.loads(line) for line in
                       (Path(temp) / "signal_history.jsonl").read_text().splitlines()]
            measured = turn_context.analyze(temp)
            self.assertEqual(json.loads((Path(temp) / "road_geometry.json").read_text())
                             ["review_status"], "candidate_only")
        self.assertEqual(receipt["frames_recorded"], 3)
        self.assertEqual([item["native_frame"] for item in source], [2, 3, 4])
        self.assertEqual(len(frames), 3)
        self.assertEqual([row["frame"] for row in crossings], [2, 3, 4])
        self.assertEqual([row["time_s"] for row in crossings],
                         [row["time_s"] for row in frames])
        self.assertEqual(crossings[0]["ego_vertices_m"],
                         crossings[0]["ego"]["body_vertices_xy_m"])
        self.assertEqual([row["frame"] for row in stops], [2, 3, 4])
        self.assertFalse(stops[0]["ego"]["body_inside_crossing"])
        self.assertFalse(stops[0]["other"]["body_inside_crossing"])
        self.assertEqual([(row["frame"], row["state"], row["other_state"])
                          for row in signals], [(2, "Green", "Red"),
                                                (3, "Green", "Red"),
                                                (4, "Green", "Red")])
        self.assertEqual([row["time_s"] for row in signals],
                         [row["time_s"] for row in frames])
        self.assertEqual(json.loads((Path(temp) / "signal_context.json").read_text())
                         ["review_status"], "candidate_only")
        self.assertTrue(measured["original_heading_complete"])
        self.assertEqual(measured["first_original_headings"]["other"]["native_lane_id"], 1)
        self.assertEqual(set(written), {name + ".mkv" for name in value["cameras"]})
        self.assertTrue(all(len(images) == 3 for images in written.values()))
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_candidate_media_requires_sourced_crossing_polygon(self):
        value = dict(site(), cameras={name: [0, 0, 10, 0, 0, 0] for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")})
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Sourced Native crossing polygon"):
                runner.capture_candidate_media(Path(temp), None, None, value, "ego",
                                               None, None, None, None, 3)

    def test_candidate_media_rejects_missing_approach_source(self):
        value = dict(site(), cameras={name: [0, 0, 10, 0, 0, 0] for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")},
                     crossing_polygon_xy_m=[[-3, -3], [3, -3], [3, 3], [-3, 3]],
                     crossing_polygon_source="synthetic fake-Native test polygon")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Native candidate junction and approach source"):
                runner.capture_candidate_media(Path(temp), None, None, value, "ego",
                                               None, None, None, None, 3)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_candidate_media_rejects_unmatched_governed_signals(self):
        value = dict(site(), cameras={name: [0, 0, 10, 0, 0, 0] for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")},
                     crossing_polygon_xy_m=[[-3, -3], [3, -3], [3, 3], [-3, 3]],
                     crossing_polygon_source="synthetic test polygon",
                     native_junction_id=77,
                     approach_headings_deg={"ego": 0, "other": 180},
                     approach_geometry_source="synthetic test route",
                     governed_signal_ids={"ego": 101, "other": 102},
                     device_inventory_source="synthetic test inventory")
        wrong = {"ego": SimpleNamespace(id=101), "other": SimpleNamespace(id=103)}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Two sourced governed Native signal actors"):
                runner.capture_candidate_media(Path(temp), None, None, value, "ego",
                                               None, None, None, None, 3,
                                               governed_lights=wrong)
            self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
