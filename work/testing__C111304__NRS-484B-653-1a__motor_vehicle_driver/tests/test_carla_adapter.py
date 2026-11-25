"""CPU stand-ins exercise source-bound CARLA calls without running CARLA."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_adapter import CarlaEncounterAdapter
from encounter import CASES, build_case


class Value:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Transform:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class Carla:
    Location = Value
    Rotation = Value
    Transform = Transform
    VehicleControl = Value


class Blueprint:
    def __init__(self, id):
        self.id = id
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Library:
    def find(self, name):
        return Blueprint(name)


class Actor:
    def __init__(self, id, blueprint, pose, parent):
        self.id, self.type_id = id, blueprint.id
        self.pose, self.parent = pose, parent
        self.blueprint = blueprint
        self.controls = []
        self.destroyed = False
        self.stopped = False
        self.callback = None

    def get_transform(self):
        return self.pose

    def get_velocity(self):
        return Value(x=2.0, y=0.0, z=0.0)

    def apply_control(self, control):
        self.controls.append(control)

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = Value(synchronous_mode=False, fixed_delta_seconds=None)
        self.actors = []
        self.frame = 99

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return Library()

    def try_spawn_actor(self, blueprint, pose, attach_to=None):
        actor = Actor(len(self.actors) + 1, blueprint, pose, attach_to)
        self.actors.append(actor)
        return actor

    def tick(self):
        self.frame += 1
        for actor in self.actors:
            if actor.callback:
                image = Value(frame=self.frame, width=2, height=2,
                              raw_data=bytes(16))
                actor.callback(image)
        return self.frame

    def get_snapshot(self):
        return Value(frame=self.frame,
                     timestamp=Value(elapsed_seconds=(self.frame - 100) / 20))


def pose(x=0, y=0, yaw=0):
    return {'x': x, 'y': y, 'z': 0, 'yaw': yaw}


def site(basis='highway'):
    lanes = {}
    for name, start, end in (
        ('northbound', pose(0, -20, 90), pose(0, 20, 90)),
        ('southbound', pose(2, 20, -90), pose(2, -20, -90)),
        ('crossing', pose(-20, 0, 0), pose(20, 0, 0)),
    ):
        lanes[name] = {'source_sha256': 'a' * 64, 'lane_id': name,
                       'waypoints': [{'source_sha256': 'b' * 64, 'transform': p}
                                     for p in (start, end)]}
    return {'cell_id': 'C111304', 'layout': 'intersection',
            'public_access_basis': basis, 'public_access_source_sha256': 'c' * 64,
            'lanes': lanes, 'conflict_zone': {'source_sha256': 'd' * 64},
            'actor_blueprints': {'ego': 'vehicle.ego', 'crossing': 'vehicle.crossing'},
            'property_anchor': {'source_sha256': 'e' * 64,
                                'blueprint_id': 'static.prop.bench',
                                'transform': pose(1, 1), 'offset_axis_xy': [1, 0]},
            'crossing_occupant': {'source_sha256': 'f' * 64,
                                  'blueprint_id': 'walker.pedestrian.0001',
                                  'relative_transform': pose(0, 0)}}


def cameras():
    return {'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                               'width': 2, 'height': 2,
                               'transform': pose()}
                        for name in ('front', 'rear', 'left', 'right')}}


class CarlaBindingTests(unittest.TestCase):
    def test_crossing_release_uses_attempt_elapsed_not_server_uptime(self):
        world = World()
        world.frame = 1000
        adapter = CarlaEncounterAdapter(world, Carla, site(), cameras())
        adapter.start()
        actors = build_case(adapter, site(), CASES[0])
        adapter.start_cameras(actors['ego'])
        adapter.tick()
        adapter.tick()
        self.assertEqual(adapter.commands[actors['crossing_vehicle'].id]['throttle'], 0.0)
        adapter.cleanup()

    def test_both_approaches_property_offset_and_camera_sources(self):
        for case in (CASES[0], CASES[2], CASES[4], CASES[5]):
            world = World()
            adapter = CarlaEncounterAdapter(world, Carla, site(), cameras())
            adapter.start()
            actors = build_case(adapter, site(), case)
            adapter.start_cameras(actors['ego'])
            self.assertTrue(world.settings.synchronous_mode)
            self.assertEqual(world.settings.fixed_delta_seconds, 0.05)
            self.assertEqual(actors['ego'].pose.location.y,
                             -20 if case.approach == 'northbound' else 20)
            self.assertEqual(actors['property'].pose.location.x,
                             1 if case.case_id == 'property_near' else 9)
            self.assertIs(actors['occupant'].parent, actors['crossing_vehicle'])
            frame, elapsed = adapter.tick()
            self.assertEqual((frame, elapsed), (100, 0.0))
            self.assertEqual(adapter.read_actor(actors['occupant'])['vehicle_id'],
                             str(actors['crossing_vehicle'].id))
            self.assertEqual(adapter.read_control(actors['ego'], actors['crossing_vehicle'])['crossing_release_s'],
                             case.crossing_release_s)
            for name in ('front', 'rear', 'left', 'right'):
                camera_frame, encoded = adapter.read_camera(name)
                self.assertEqual(camera_frame, frame)
                self.assertTrue(encoded.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(adapter.cameras[name].blueprint.attributes['sensor_tick'], '0.05')
            adapter.cleanup()
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertTrue(all(actor.stopped for actor in adapter.cameras.values()))

    def test_missing_reviewed_source_and_camera_mismatch_rejected(self):
        world = World()
        bad = cameras()
        del bad['cameras']['rear']
        with self.assertRaisesRegex(ValueError, 'four reviewed camera sources'):
            CarlaEncounterAdapter(world, Carla, site(), bad).start()
        adapter = CarlaEncounterAdapter(world, Carla, site(), cameras())
        adapter.start()
        bad_site = site()
        del bad_site['lanes']['northbound']['waypoints'][0]['source_sha256']
        with self.assertRaisesRegex(ValueError, 'lane waypoint source hash'):
            build_case(adapter, bad_site, CASES[0])
        adapter.cleanup()

    def test_original_camera_png_is_saved_with_readback_bytes(self):
        world = World()
        adapter = CarlaEncounterAdapter(world, Carla, site(), cameras())
        with TemporaryDirectory() as tmp:
            output = Path(tmp)
            adapter.start()
            actors = build_case(adapter, site(), CASES[0])
            adapter.start_cameras(actors['ego'], output)
            frame, _ = adapter.tick()
            for name in ('front', 'rear', 'left', 'right'):
                camera_frame, encoded = adapter.read_camera(name)
                self.assertEqual(camera_frame, frame)
                self.assertEqual((output / 'cameras' / name / f'{frame:06d}.png').read_bytes(), encoded)
            adapter.cleanup()


if __name__ == '__main__':
    unittest.main()
