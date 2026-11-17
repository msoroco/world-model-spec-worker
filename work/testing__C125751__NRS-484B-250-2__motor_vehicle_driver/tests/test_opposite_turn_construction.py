import importlib.util
import hashlib
import json
import tempfile
import unittest
import turn_context
import stop_measurements
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from shapely.geometry import Polygon


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
            "crossing_polygon_xy_m": [[-3, -3], [3, -3], [3, 3], [-3, 3]],
            "expected_approach_lanes": {"ego": [11, -1], "other": [11, 1]}}


def stop_references():
    return {role: {"kind": "marked_stop_line",
                   "segment_xy_m": [[x, -2], [x, 2]],
                   "geometry_source": "synthetic fake-Native line",
                   "reference_review_source": "synthetic fake-Native review"}
            for role, x in (("ego", -5), ("other", 5))}


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

    def test_rejects_routes_outside_sourced_crossing_before_spawn(self):
        changed = site()
        changed["crossing_polygon_xy_m"] = [[20, 20], [26, 20], [26, 26], [20, 26]]
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        with self.assertRaisesRegex(ValueError, "Route does not enter and leave sourced crossing"):
            with module.construct_opposite_turn_pair(World(actors),
                                                     {"ego": "car", "other": "car"},
                                                     {"ego": "pose1", "other": "pose2"},
                                                     changed, "ego"):
                pass
        self.assertFalse(any(hasattr(actor, "control") for actor in actors))

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

    def test_bad_crossing_applies_no_partial_command(self):
        actors = {"ego": Actor([11, -1], 0), "other": Actor([11, 1], 180)}
        changed = site()
        changed["crossing_polygon_xy_m"] = [[20, 20], [26, 20], [26, 26], [20, 26]]
        carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace())
        with self.assertRaisesRegex(ValueError, "Route does not enter and leave sourced crossing"):
            module.command_opposite_turn_pair(
                carla, actors, changed, {"ego": 1, "other": 1}, 8,
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
                     native_map_name="SyntheticTown",
                     device_inventory_source="synthetic fake-Native signal inventory",
                     selected_stop_references=stop_references())
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
            measured_device = runner.analyze_device_sources(temp)
            self.assertEqual(json.loads((Path(temp) / "road_geometry.json").read_text())
                             ["review_status"], "candidate_only")
            signal_context = json.loads((Path(temp) / "signal_context.json").read_text())
            self.assertEqual(signal_context["review_status"], "candidate_only")
            self.assertEqual(signal_context["governed_lane_id"], -1)
            stop_context = json.loads((Path(temp) / "stop_context.json").read_text())
            self.assertEqual(stop_context["selected_references"], stop_references())
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
        self.assertTrue(measured["original_heading_complete"])
        self.assertEqual([row["frame"] for row in measured_device["observations"]], [2, 3, 4])
        self.assertEqual(measured_device["native_signal_ids"], {"ego": 101, "other": 102})
        self.assertEqual(measured_device["selected_stop_references"], stop_references())
        self.assertEqual(measured_device["official_device_judgment"], "unresolved")
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
                     native_map_name="SyntheticTown",
                     device_inventory_source="synthetic test inventory")
        wrong = {"ego": SimpleNamespace(id=101), "other": SimpleNamespace(id=103)}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Two sourced governed Native signal actors"):
                runner.capture_candidate_media(Path(temp), None, None, value, "ego",
                                               None, None, None, None, 3,
                                               governed_lights=wrong)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_candidate_media_rejects_missing_stop_reference_before_writing(self):
        value = dict(site(), cameras={name: [0, 0, 10, 0, 0, 0] for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")},
                     crossing_polygon_xy_m=[[-3, -3], [3, -3], [3, 3], [-3, 3]],
                     crossing_polygon_source="synthetic polygon",
                     native_junction_id=77,
                     approach_headings_deg={"ego": 0, "other": 180},
                     approach_geometry_source="synthetic route")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Source-selected stop references"):
                runner.capture_candidate_media(Path(temp), None, None, value, "ego",
                                               None, None, None, None, 3)
            self.assertEqual(list(Path(temp).iterdir()), [])


class DeviceSourceJoinTests(unittest.TestCase):
    def _sources(self, root):
        (root / "turn_route_context.json").write_text(json.dumps({
            "intersection_id": 7, "routes": {
                "ego": [[-10, 0], [-4, 0], [0, 0], [10, 0]],
                "other": [[0, -10], [0, -4], [0, 0], [0, 10]]}}))
        (root / "road_geometry.json").write_text(json.dumps({
            "intersection_id": 7, "ego_approach_heading_deg": 0,
            "other_approach_heading_deg": 90,
            "intersection_polygon_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]]}))
        (root / "signal_context.json").write_text(json.dumps({
            "intersection_id": 7, "native_map_id": "TownSynthetic",
            "native_signal_id": 17, "other_native_signal_id": 18,
            "governed_road_id": 1, "governed_lane_id": -1,
            "other_governed_road_id": 2, "other_governed_lane_id": -1,
            "device_inventory_source": "synthetic candidate inventory",
            "review_status": "candidate_only"}))
        (root / "stop_context.json").write_text(json.dumps({
            "intersection_id": 7, "selected_references": stop_references(),
            "review_status": "candidate_only"}))
        rows = [{"frame": 100+i, "time_s": i*.05,
                 "ego": {"heading_deg": 0, "native_road_id": 1, "native_lane_id": -1,
                         "velocity_xyz_mps": [float(i), 0., 0.], "speed_mps": float(i),
                         "body_vertices_xy_m": [[-10+i, -1], [-10+i, 1],
                                                [-6+i, -1], [-6+i, 1]]},
                 "other": {"heading_deg": 90, "native_road_id": 2, "native_lane_id": -1,
                           "velocity_xyz_mps": [float(i), 0., 0.], "speed_mps": float(i),
                           "body_vertices_xy_m": [[6-i, -1], [6-i, 1],
                                                  [10-i, -1], [10-i, 1]]}}
                for i in range(2)]
        signals = [{"frame": 100+i, "time_s": i*.05, "native_signal_id": 17,
                    "other_native_signal_id": 18, "state": "Off", "other_state": "Off"}
                   for i in range(2)]
        polygon = Polygon([[-2, -2], [2, -2], [2, 2], [-2, 2]])
        stops = [{"frame": row["frame"], "time_s": row["time_s"],
                  "ego": runner._stop_state(row["ego"], polygon),
                  "other": runner._stop_state(row["other"], polygon)} for row in rows]
        frames = [{"carla_frame": 100+i, "time_s": i*.05, "video_frame": i}
                  for i in range(2)]
        for name, values in (("crossing_history.jsonl", rows),
                             ("signal_history.jsonl", signals),
                             ("stop_history.jsonl", stops),
                             ("video_frames.jsonl", frames)):
            (root / name).write_text("".join(json.dumps(x)+"\n" for x in values))

    def test_candidate_stop_context_feeds_saved_stop_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self._sources(root)
            entries = {"intersection_id": 7, "first_body_entry": {
                "ego": {"frame": 101, "time_s": .05},
                "other": {"frame": 100, "time_s": 0.}}}
            measured = stop_measurements.analyze(root, entries)
            self.assertEqual(measured["first_recorded_zero_speed_before_entry"]["ego"]["frame"], 100)
            self.assertIsNone(measured["first_recorded_zero_speed_before_entry"]["other"])
            self.assertEqual(measured["statutory_stop_judgment"], "unresolved")

    def test_device_join_rejects_missing_tampered_and_changed_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self._sources(root)
            self.assertEqual(len(runner.analyze_device_sources(root)["observations"]), 2)
            (root / "stop_history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing opposite-turn device source"):
                runner.analyze_device_sources(root)
            self._sources(root)
            signals = [json.loads(x) for x in (root / "signal_history.jsonl").read_text().splitlines()]
            signals[1]["native_signal_id"] = 99
            (root / "signal_history.jsonl").write_text("".join(json.dumps(x)+"\n" for x in signals))
            with self.assertRaisesRegex(ValueError, "signal identity/state"):
                runner.analyze_device_sources(root)
            self._sources(root)
            context = json.loads((root / "signal_context.json").read_text())
            context["other_governed_lane_id"] = 8
            (root / "signal_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "differs from governed signal lane"):
                runner.analyze_device_sources(root)
            self._sources(root)
            stop_context = json.loads((root / "stop_context.json").read_text())
            stop_context["selected_references"]["ego"]["segment_xy_m"] = [[0, 0], [0, 0]]
            (root / "stop_context.json").write_text(json.dumps(stop_context))
            with self.assertRaisesRegex(ValueError, "nondegenerate stop reference"):
                runner.analyze_device_sources(root)
            self._sources(root)
            hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in (*turn_context.SOURCES, *runner.DEVICE_SOURCES)}
            (root / "result.json").write_text(json.dumps({"source_evidence_hashes": hashes}))
            (root / "signal_history.jsonl").write_text((root / "signal_history.jsonl").read_text()+" ")
            with self.assertRaisesRegex(ValueError, "differs from saved result"):
                runner.analyze_device_sources(root)

    def test_device_join_recomputes_stop_observations_from_original_bodies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for changed, error in (("speed_mps", "body geometry"),
                                   ("front_xy_m", "body geometry"),
                                   ("body_inside_crossing", "body geometry")):
                self._sources(root)
                rows = [json.loads(line) for line in (root / "stop_history.jsonl").read_text().splitlines()]
                if changed == "speed_mps":
                    rows[1]["ego"][changed] += 1.
                elif changed == "front_xy_m":
                    rows[1]["ego"][changed][0] += 1.
                else:
                    rows[1]["ego"][changed] = True
                (root / "stop_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
                with self.assertRaisesRegex(ValueError, error):
                    runner.analyze_device_sources(root)
            self._sources(root)
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            rows[1]["ego"]["speed_mps"] = 7.
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "speed differs from velocity"):
                runner.analyze_device_sources(root)

    def _opposite_entry_sources(self, root):
        self._sources(root)
        route = json.loads((root / "turn_route_context.json").read_text())
        route["routes"] = {"ego": [[-10, 0], [-4, 0], [0, 0], [0, 10]],
                           "other": [[10, 0], [4, 0], [0, 0], [-10, 0]]}
        (root / "turn_route_context.json").write_text(json.dumps(route))
        road = json.loads((root / "road_geometry.json").read_text())
        road["other_approach_heading_deg"] = 180
        (root / "road_geometry.json").write_text(json.dumps(road))
        rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
        for row in rows:
            row["other"]["heading_deg"] = 180
        rows[1]["ego"]["body_vertices_xy_m"] = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
        rows[1]["other"]["body_vertices_xy_m"] = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
        (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        polygon = Polygon(road["intersection_polygon_xy_m"])
        stops = [json.loads(line) for line in (root / "stop_history.jsonl").read_text().splitlines()]
        for row, stop in zip(rows, stops):
            for role in ("ego", "other"):
                stop[role] = runner._stop_state(row[role], polygon)
        (root / "stop_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in stops))
        body_rows = [{"native_frame": row["frame"], "frame_index": index,
                      "turning_role": "ego", "actor_sources": {role: row[role] for role in ("ego", "other")},
                      "camera_source_frames": {name: row["frame"] for name in
                                               ("overview", "approach", "reference_corner", "driver_reference")}}
                     for index, row in enumerate(rows)]
        (root / "body_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in body_rows))

    def test_opposite_candidate_entry_uses_original_body_and_camera_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self._opposite_entry_sources(root)
            entry = runner.analyze_candidate_opposite_entry(root)
            self.assertEqual(entry["turning_role"], "ego")
            self.assertEqual(entry["first_body_entry"], {
                "ego": {"frame": 101, "time_s": .05},
                "other": {"frame": 101, "time_s": .05}})
            self.assertEqual(entry["turning_minus_other_entry_time_s"], 0)
            self.assertEqual(entry["construction_geometry"]["approach_separation_deg"], 180)
            self.assertEqual(entry["signal_at_body_entry"]["ego"]["native_state"], "Off")
            self.assertEqual(entry["signal_at_body_entry"]["other"]["native_signal_id"], 18)
            self.assertEqual(entry["stop_order"]["first_recorded_zero_speed_before_entry"]["ego"]["frame"], 100)
            self.assertEqual(entry["stop_order"]["statutory_yield_judgment"], "unresolved")
            self.assertEqual(entry["statutory_exception_judgment"], "unresolved")
            self.assertFalse(entry["physical_acceptance_claimed"])
            (root / "result.json").write_text(json.dumps({"source_evidence_hashes": entry["source_hashes"]}))
            self.assertEqual(runner.analyze_candidate_opposite_entry(root)["first_body_entry"], entry["first_body_entry"])
            (root / "body_history.jsonl").write_text((root / "body_history.jsonl").read_text()+" ")
            with self.assertRaisesRegex(ValueError, "body source differs from saved result"):
                runner.analyze_candidate_opposite_entry(root)
            (root / "result.json").unlink()
            (root / "body_history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original opposite-turn body history"):
                runner.analyze_candidate_opposite_entry(root)

    def test_opposite_candidate_entry_rejects_camera_and_actor_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self._opposite_entry_sources(root)
            rows = [json.loads(line) for line in (root / "body_history.jsonl").read_text().splitlines()]
            rows[1]["camera_source_frames"]["overview"] += 1
            (root / "body_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "body/camera original-frame join"):
                runner.analyze_candidate_opposite_entry(root)
            self._opposite_entry_sources(root)
            rows = [json.loads(line) for line in (root / "body_history.jsonl").read_text().splitlines()]
            rows[1]["actor_sources"]["ego"]["native_lane_id"] = 5
            (root / "body_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "body/camera original-frame join"):
                runner.analyze_candidate_opposite_entry(root)

    def test_opposite_candidate_entry_rejects_start_inside_crossing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self._opposite_entry_sources(root)
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            rows[0]["ego"]["body_vertices_xy_m"] = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            body_rows = [json.loads(line) for line in (root / "body_history.jsonl").read_text().splitlines()]
            body_rows[0]["actor_sources"]["ego"] = rows[0]["ego"]
            (root / "body_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in body_rows))
            stop_rows = [json.loads(line) for line in (root / "stop_history.jsonl").read_text().splitlines()]
            stop_rows[0]["ego"] = runner._stop_state(rows[0]["ego"], Polygon([[-2, -2], [2, -2], [2, 2], [-2, 2]]))
            (root / "stop_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in stop_rows))
            with self.assertRaisesRegex(ValueError, "starts inside crossing"):
                runner.analyze_candidate_opposite_entry(root)


if __name__ == "__main__":
    unittest.main()
