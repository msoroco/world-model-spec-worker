import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_construction import stage_case
from officer_source import (BLUEPRINT_ID, apply_direction_pose, read_direction_pose,
                            spawn_candidate, write_candidate_packet)
from yield_stage import PREFIX, primary


class Actors:
    def __init__(self, other_stop):
        self.other_stop = other_stop

    def filter(self, pattern):
        if pattern == "traffic.stop*" and not self.other_stop:
            return []
        return [NS(id=90 if pattern == "traffic.stop*" else 88,
                   trigger_volume=NS(contains=lambda point, transform: True),
                   get_transform=lambda: None)]


class World:
    def __init__(self, other_stop=False):
        self.actors = Actors(other_stop)
        self.destroyed = []
        self.spawned = []
        self.probes = {(-20, 1.8): (158208, -1, False),
                       (0, 1.8): (158210, -1, True),
                       (1.8, 20): (158212, -1, False),
                       (1.8, 0): (158213, -1, True),
                       (-1.8, -20): (158214, 1, False),
                       (-60, 1.8): (158208, -1, False),
                       (1.8, -4): (158213, -1, True),
                       (1.8, 25): (158212, -1, False)}

    def get_map(self):
        return NS(name="signed-map", get_waypoint=self.get_waypoint)

    def get_waypoint(self, location, project_to_road=False):
        road, lane, junction = self.probes[(location.x, location.y)]
        return NS(road_id=road, lane_id=lane, is_junction=junction,
                  transform=NS(location=location))

    def get_actors(self):
        return self.actors

    def get_blueprint_library(self):
        return NS(find=lambda blueprint: blueprint)

    def try_spawn_actor(self, blueprint, transform):
        actor = NS(id=len(self.spawned) + 1, type_id=blueprint,
                   get_location=lambda: transform.location,
                   destroy=lambda: self.destroyed.append(transform.location))
        self.spawned.append(actor)
        return actor


class ConstructionTests(unittest.TestCase):
    location = staticmethod(lambda x, y, z: NS(x=x, y=y, z=z))

    def test_inside_approaching_and_obligated_spawn_on_different_native_lanes(self):
        for kind, other_stop, expected_road in (("yield_other_inside", False, 158213),
                                                ("yield_other_approaching", False, 158212),
                                                ("yield_other_obligated", True, 158213)):
            world = World(other_stop)
            with stage_case(world, primary(PREFIX + kind), location_factory=self.location) as actors:
                self.assertEqual(len(world.spawned), 2)
                self.assertEqual(world.get_waypoint(actors["other"].get_location()).road_id, expected_road)
                self.assertEqual(actors["site"]["native_other_stop_sign_id"], 90 if other_stop else None)
            self.assertEqual(len(world.destroyed), 2)

    def test_officer_case_refuses_unsourced_actor_and_cleans_up(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "sourced Native officer"):
            with stage_case(world, primary(PREFIX + "officer_control_exception"),
                            location_factory=self.location):
                pass
        self.assertEqual(len(world.destroyed), 2)

    def test_officer_candidate_is_spawned_identified_and_owned(self):
        world = World()
        vehicle_spawn = world.try_spawn_actor
        world.get_blueprint_library = lambda: NS(find=lambda name: NS(id=name))

        def spawn(blueprint, transform):
            if blueprint.id == BLUEPRINT_ID:
                actor = NS(id=17, type_id=BLUEPRINT_ID,
                           get_location=lambda: transform.location,
                           destroy=lambda: world.destroyed.append(transform.location))
                world.spawned.append(actor)
                return actor
            return vehicle_spawn(blueprint.id, transform)

        world.try_spawn_actor = spawn
        factory = lambda native, location: spawn_candidate(
            native, location_factory=location,
            rotation_factory=lambda yaw: NS(yaw=yaw),
            transform_factory=lambda position, rotation: NS(location=position, rotation=rotation))
        with stage_case(world, primary(PREFIX + "officer_control_exception"),
                        location_factory=self.location, officer_factory=factory) as actors:
            self.assertEqual(actors["officer"].id, 17)
            self.assertEqual(actors["officer"].get_location().x, 6.0)
            with __import__("tempfile").TemporaryDirectory() as tmp:
                pose = {"bone": "crl_shoulder__R", "pitch_offset_deg": -70.0,
                        "commanded_relative_rotation_deg":
                            {"pitch": -70.0, "yaw": 0.0, "roll": 0.0}}
                packet = write_candidate_packet(
                    tmp, actors["officer"], pose_command=pose,
                    pose_readback=pose["commanded_relative_rotation_deg"])
                record = __import__("json").loads(packet.read_text())
                self.assertEqual(record["actor_id"], 17)
                self.assertEqual(record["blueprint_id"], "walker.pedestrian.0030")
                self.assertEqual(record["direction_pose_command"], pose)
                self.assertEqual(record["police_authority_judgment"], "unresolved")
        self.assertEqual(len(world.destroyed), 3)

    def test_officer_direction_pose_requires_native_bone_readback(self):
        baseline = NS(location=NS(x=0, y=0, z=0),
                      rotation=NS(pitch=10.0, yaw=2.0, roll=3.0))
        state = {"relative": baseline, "shown": False}
        actor = NS(get_bones=lambda: NS(bone_transforms=[
                       ("crl_shoulder__R", None, None, state["relative"])]),
                   get_pose_from_animation=lambda: None,
                   set_bones=lambda control: state.update(relative=control[0][1]),
                   show_pose=lambda: state.update(shown=True))
        command = apply_direction_pose(
            actor, transform_factory=lambda location, rotation:
                NS(location=location, rotation=rotation),
            rotation_factory=lambda pitch, yaw, roll: NS(
                pitch=pitch, yaw=yaw, roll=roll),
            bone_control_factory=lambda rows: rows)
        self.assertTrue(state["shown"])
        self.assertEqual(read_direction_pose(actor, command)["pitch"], -60.0)
        state["relative"].rotation.pitch = -40.0
        with self.assertRaisesRegex(ValueError, "readback differs"):
            read_direction_pose(actor, command)


if __name__ == "__main__":
    unittest.main()
