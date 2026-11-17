"""Synthetic CPU checks for the unselected combination construction draft."""

import importlib.util
import copy
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "combination_construction.py"
SPEC = importlib.util.spec_from_file_location("combination_construction", SOURCE)
combination = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combination)
MEASURE_SPEC = importlib.util.spec_from_file_location("truck_measurements", SOURCE.with_name("truck_measurements.py"))
measurements = importlib.util.module_from_spec(MEASURE_SPEC)
MEASURE_SPEC.loader.exec_module(measurements)


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Box:
    def __init__(self, width, length):
        self.width, self.length = width, length

    def get_world_vertices(self, actor):
        return [Point(actor.x + dx, actor.y + dy)
                for dx in (-self.length / 2, self.length / 2)
                for dy in (-self.width / 2, self.width / 2)]


class Actor:
    def __init__(self, x, y, width, length, parent=None):
        self.x, self.y, self.parent = x, y, parent
        self.bounding_box = Box(width, length)
        self.destroyed = False

    def get_transform(self):
        return self

    def get_location(self):
        return self

    def get_velocity(self):
        return type("Velocity", (), {"x": 12.0, "y": 0.0, "z": 0.0})()

    def destroy(self):
        self.destroyed = True


class Map:
    def get_waypoint(self, location, project_to_road=False):
        if project_to_road or abs(location.y + 1.9) > 0.01:
            return None
        return type("Waypoint", (), {"road_id": 4, "lane_id": -1})()


class World:
    def __init__(self, fail_trailer=False):
        self.actors = []
        self.fail_trailer = fail_trailer

    def try_spawn_actor(self, blueprint, transform, attach_to=None, attachment_type=None):
        if attach_to is not None and (self.fail_trailer or attachment_type != "Rigid"):
            return None
        x = transform["x"] + (attach_to.x if attach_to else 0)
        y = transform["y"] + (attach_to.y if attach_to else 0)
        actor = Actor(x, y, transform["width"], transform["length"], attach_to)
        actor.id = len(self.actors) + 1
        actor.type_id = blueprint
        self.actors.append(actor)
        return actor

    def tick(self):
        return 1

    def get_map(self):
        return Map()


def inputs(width=2.2, hitch_x=-10):
    blueprints = {role: {"tractor": role + "-tractor", "trailer": role + "-trailer"}
                  for role in ("ego", "lead")}
    transforms = {
        role: {"tractor": {"x": x, "y": -1.9, "width": width, "length": 4},
               "trailer": {"x": hitch_x, "y": 0, "width": width, "length": 8}}
        for role, x in (("ego", 100), ("lead", 300))}
    return blueprints, transforms


class CombinationConstructionTests(unittest.TestCase):
    def test_original_frame_capture_reads_moving_attached_components(self):
        class MovingWorld(World):
            frame = 100

            def tick(self):
                self.frame += 1
                for actor in self.actors:
                    actor.x += 1
                return self.frame

        world = MovingWorld()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0]) as pair:
            commands = []
            rows = combination.capture_combination_history(
                world, pair["actors"], lambda index, actors: commands.append(index),
                road_id=4, lane_id=-1, lane_forward_xy=[1, 0], frames=3)
            self.assertEqual(commands, [0, 1, 2])
            self.assertEqual([row["frame"] for row in rows], [102, 103, 104])
            self.assertEqual([row["time_s"] for row in rows], [0, .05, .1])
            self.assertEqual(rows[-1]["ego"]["components"]["trailer"]["actor_id"], 2)
            self.assertEqual(len(rows[-1]["lead"]["components"]["tractor"]["body_vertices_xy_m"]), 4)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_original_frame_capture_rejects_unobserved_motion(self):
        class StaticWorld(World):
            frame = 100

            def tick(self):
                self.frame += 1
                return self.frame

        world = StaticWorld()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0]) as pair:
            with self.assertRaisesRegex(ValueError, "motion absent"):
                combination.capture_combination_history(
                    world, pair["actors"], lambda index, actors: None,
                    road_id=4, lane_id=-1, lane_forward_xy=[1, 0], frames=3)

    def test_original_frame_capture_rejects_stationary_trailer(self):
        class DetachedWorld(World):
            frame = 100

            def tick(self):
                self.frame += 1
                for actor in self.actors:
                    if actor.parent is None:
                        actor.x += .1
                return self.frame

        world = DetachedWorld()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0]) as pair:
            with self.assertRaisesRegex(ValueError, "motion absent: ego/trailer"):
                combination.capture_combination_history(
                    world, pair["actors"], lambda index, actors: None,
                    road_id=4, lane_id=-1, lane_forward_xy=[1, 0], frames=3)

    def test_pair_measures_combined_body_gap_and_releases_all_actors(self):
        world = World()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0]) as pair:
            self.assertAlmostEqual(pair["initial_longitudinal_body_gap_m"], 184)
            self.assertFalse(pair["native_attachment_verified"])
            self.assertFalse(pair["legal_vehicle_class_verified"])
            self.assertEqual(len(world.actors), 4)
            self.assertIs(world.actors[1].parent, world.actors[0])
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_failed_attachment_cleans_up_owned_tractor(self):
        world = World(fail_trailer=True)
        blueprints, transforms = inputs()
        with self.assertRaisesRegex(ValueError, "trailer attachment failed"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertEqual(len(world.actors), 1)
        self.assertTrue(world.actors[0].destroyed)

    def test_rejects_subthreshold_combined_width(self):
        world = World()
        blueprints, transforms = inputs(width=1.9)
        with self.assertRaisesRegex(ValueError, "below 80-inch width"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_unjoined_trailer_geometry(self):
        world = World()
        blueprints, transforms = inputs(hitch_x=-30)
        with self.assertRaisesRegex(ValueError, "planned hitch"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_selected_gap_uses_combined_body_extents_and_rejects_drift(self):
        blueprints, transforms = inputs()
        transforms["lead"]["tractor"]["x"] = 268.4
        world = World()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0], expected_body_gap_m=152.4,
            gap_tolerance_m=0.01) as pair:
            self.assertAlmostEqual(pair["initial_longitudinal_body_gap_m"], 152.4)
            self.assertEqual(pair["expected_body_gap_m"], 152.4)
        self.assertTrue(all(actor.destroyed for actor in world.actors))
        drifted = World()
        transforms["lead"]["tractor"]["x"] = 270
        with self.assertRaisesRegex(ValueError, "differs from selected target"):
            with combination.spawn_combination_pair(
                drifted, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0], expected_body_gap_m=152.4,
                gap_tolerance_m=0.01):
                pass
        self.assertTrue(all(actor.destroyed for actor in drifted.actors))

    def test_measured_lead_placement_hits_500_foot_body_gap(self):
        world = World()
        blueprints, transforms = inputs()
        placements = []

        def place_lead(actors, delta, tangent):
            placements.append((delta, tangent))
            actors["tractor"].x += delta
            actors["trailer"].x += delta

        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0], expected_body_gap_m=152.4,
            gap_tolerance_m=.01, position_lead=place_lead) as pair:
            self.assertAlmostEqual(pair["initial_longitudinal_body_gap_m"], 152.4)
            self.assertAlmostEqual(placements[0][0], -31.6)
            self.assertEqual(placements[0][1], (1., 0.))
        self.assertTrue(all(actor.destroyed for actor in world.actors))

        drifted = World()
        with self.assertRaisesRegex(ValueError, "differs from selected target"):
            with combination.spawn_combination_pair(
                drifted, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0], expected_body_gap_m=152.4,
                gap_tolerance_m=.01,
                position_lead=lambda actors, delta, tangent: None):
                pass
        self.assertTrue(all(actor.destroyed for actor in drifted.actors))

    def test_trailer_outside_selected_lane_is_rejected(self):
        world = World()
        blueprints, transforms = inputs()
        transforms["lead"]["trailer"]["y"] = 2
        with self.assertRaisesRegex(ValueError, "outside selected lane"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0], expected_body_gap_m=184):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_original_component_row_retains_both_bodies_and_rejects_lane_forgery(self):
        world = World()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0], expected_body_gap_m=184) as pair:
            waypoint = type("Waypoint", (), {"road_id": 4, "lane_id": -1})()
            lanes = {role: {part: waypoint for part in ("tractor", "trailer")}
                     for role in ("ego", "lead")}
            row = combination.combination_source_row(
                pair["actors"], lanes, [1, 0], 4, -1, 81, 4.05)
            self.assertEqual((row["frame"], row["time_s"]), (81, 4.05))
            self.assertEqual(len(row["ego"]["body_vertices_xy_m"]), 8)
            self.assertEqual(row["ego"]["overall_width_m"], 2.2)
            self.assertEqual(row["lead"]["components"]["trailer"]["actor_id"], 4)
            self.assertEqual(row["ego"]["velocity_mps"], [12.0, 0.0, 0.0])
            self.assertEqual(row["ego"]["components"]["trailer"]["velocity_mps"], [12.0, 0.0, 0.0])
            self.assertFalse(row["lead"]["legal_vehicle_class_verified"])
            audit = combination.audit_combination_source_row(row, [1, 0], 4, -1)
            self.assertEqual(audit["longitudinal_body_gap_m"], 184)
            forged = copy.deepcopy(row)
            forged["ego"]["overall_width_m"] = 3.0
            with self.assertRaisesRegex(ValueError, "width differs"):
                combination.audit_combination_source_row(forged, [1, 0], 4, -1)
            forged = copy.deepcopy(row)
            forged["lead"]["components"].pop("trailer")
            with self.assertRaisesRegex(ValueError, "Missing saved combination component"):
                combination.audit_combination_source_row(forged, [1, 0], 4, -1)
            forged = copy.deepcopy(row)
            forged["lead"]["components"]["trailer"]["velocity_mps"] = [float("nan"), 0, 0]
            with self.assertRaisesRegex(ValueError, "Missing saved combination velocity"):
                combination.audit_combination_source_row(forged, [1, 0], 4, -1)
            forged = copy.deepcopy(row)
            forged["ego"]["velocity_mps"] = [0, 0, 0]
            with self.assertRaisesRegex(ValueError, "tractor identity or velocity differs"):
                combination.audit_combination_source_row(forged, [1, 0], 4, -1)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "truck_history.jsonl").write_text(json.dumps(row) + "\n")
                (root / "video_frames.jsonl").write_text(json.dumps({
                    "video_frame": 0, "carla_frame": 81, "time_s": 4.05}) + "\n")
                (root / "road_context.json").write_text(json.dumps({
                    "native_map_id": "diagnostic", "road_id": 4, "lane_id": -1,
                    "same_direction_lane_count": 1, "lane_forward_xy": [1, 0],
                    "lane_count_source": "fake Native lane"}))
                report = measurements.analyze(root)
                self.assertEqual(report["samples"][0]["longitudinal_body_gap_m"], 184)
                self.assertTrue(report["samples"][0]["ego"]["is_truck_or_combination"])
            lanes["lead"]["trailer"] = type("Waypoint", (), {"road_id": 4, "lane_id": -2})()
            with self.assertRaisesRegex(ValueError, "lane mismatch"):
                combination.combination_source_row(
                    pair["actors"], lanes, [1, 0], 4, -1, 82, 4.1)


if __name__ == "__main__":
    unittest.main()
