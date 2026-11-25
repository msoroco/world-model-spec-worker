"""CPU fakes for source-bound vehicle placement and requested control."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_right_control import make_controller, spawn_four_cameras, spawn_source_actors, station_to_world
from pass_right_route import build_case
from test_pass_right_actor import packet


class Vehicle:
    def __init__(self, actor_id, x, y):
        self.id = actor_id
        self.is_alive = True
        self.transform = N(location=N(x=x, y=y), rotation=N(yaw=0.0))
        self.velocity = N(x=0.0, y=0.0)
        self.controls = []
        self.lights = 0
        self.destroyed = False

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def apply_control(self, command):
        self.controls.append(command)

    def get_light_state(self):
        return self.lights

    def set_light_state(self, state):
        self.lights = state

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_second=False):
        self.spawned = []
        self.fail_second = fail_second

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and len(self.spawned) == 1:
            return None
        actor = Vehicle(len(self.spawned) + 1, transform.location.x, transform.location.y)
        self.spawned.append(actor)
        return actor

    def spawn_actor(self, blueprint, transform, attach_to):
        return self.try_spawn_actor(blueprint, transform)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.source = packet()

    def test_source_world_right_positive_and_bounds(self):
        self.assertEqual(station_to_world(self.source, 60.0, 3.0), (60.0, 7.0, 0.0))
        with self.assertRaisesRegex(ValueError, 'outside source-reviewed'):
            station_to_world(self.source, 90, 0)
        with self.assertRaisesRegex(ValueError, 'leaves original pavement'):
            station_to_world(self.source, 60, 4.3)
        bad = packet()
        bad['cross_sections'][2]['world_center_xy_m'] = [100, 10]
        with self.assertRaisesRegex(ValueError, 'polyline length'):
            station_to_world(bad, 60, 0)

    def test_spawns_both_and_cleans_partial_failure(self):
        case = build_case(self.source, 'left_signal')
        kwargs = dict(blueprint_library=N(find=lambda name: name),
                      transform_factory=lambda location, rotation: N(location=location, rotation=rotation),
                      location_factory=lambda **fields: N(**fields),
                      rotation_factory=lambda **fields: N(**fields),
                      ego_blueprint_id='vehicle.ego', target_blueprint_id='vehicle.target',
                      ego_start_s_m=50, target_start_s_m=55)
        world = World()
        ego, target = spawn_source_actors(world, self.source, case, **kwargs)
        self.assertEqual((ego.transform.location.y, target.transform.location.y), (7.0, 10.0))
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            spawn_source_actors(World(fail_second=True), self.source, case, **kwargs)
        failed = World(fail_second=True)
        with self.assertRaises(ValueError):
            spawn_source_actors(failed, self.source, case, **kwargs)
        self.assertTrue(failed.spawned[0].destroyed)
        with self.assertRaisesRegex(ValueError, 'ahead'):
            spawn_source_actors(World(), self.source, case,
                                **{**kwargs, 'target_start_s_m': 51})

    def test_signal_motion_requests_are_distinct_and_readback_is_not_faked(self):
        for variant, expected_signal in [('left_signal', True), ('left_turn', False), ('neither', False)]:
            case = build_case(self.source, variant)
            ego, target = Vehicle(1, 50, 7), Vehicle(2, 55, 10)
            callback = make_controller(ego, target, self.source, case,
                                       control_factory=lambda **fields: fields,
                                       left_signal_mask=0x20, ego_speed_mps=4,
                                       target_speed_mps=2)
            callback(0)
            self.assertEqual(bool(target.lights & 0x20), expected_signal)
            self.assertEqual(len(ego.controls), 1)
            self.assertEqual(len(target.controls), 1)
            self.assertGreater(ego.controls[0]['throttle'], 0)
            self.assertEqual(target.transform.location.y, 10)
            self.assertGreaterEqual(ego.controls[0]['steer'], -0.01)
            if variant == 'left_turn':
                self.assertGreater(target.controls[0]['steer'], 0)
            else:
                self.assertAlmostEqual(target.controls[0]['steer'], 0)
            with self.assertRaisesRegex(ValueError, 'tick index'):
                callback(-1)

    def test_four_camera_profile_and_partial_cleanup(self):
        class Blueprint:
            def __init__(self):
                self.attributes = {}

            def set_attribute(self, key, value):
                self.attributes[key] = value

        blueprints = []

        def find(name):
            self.assertEqual(name, 'sensor.camera.rgb')
            result = Blueprint()
            blueprints.append(result)
            return result

        mounts = {name: {'x': 0, 'y': 0, 'z': 1.5, 'yaw': yaw, 'pitch': 0}
                  for name, yaw in [('front', 0), ('rear', 180), ('left', 90), ('right', -90)]}
        kwargs = dict(blueprint_library=N(find=find),
                      transform_factory=lambda location, rotation: N(location=location, rotation=rotation),
                      location_factory=lambda **fields: N(**fields),
                      rotation_factory=lambda **fields: N(**fields), mounts=mounts)
        sensors = spawn_four_cameras(World(), Vehicle(1, 50, 7), **kwargs)
        self.assertEqual(set(sensors), set(mounts))
        self.assertEqual(blueprints[0].attributes['image_size_x'], '1920')
        self.assertEqual(blueprints[1].attributes['image_size_x'], '1280')
        self.assertTrue(all(bp.attributes['sensor_tick'] == '0.05' for bp in blueprints))
        failed = World(fail_second=True)
        with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
            spawn_four_cameras(failed, Vehicle(1, 50, 7), **kwargs)
        self.assertTrue(failed.spawned[0].destroyed)
        with self.assertRaisesRegex(ValueError, 'four reviewed'):
            spawn_four_cameras(World(), Vehicle(1, 50, 7),
                               **{**kwargs, 'mounts': {'front': mounts['front']}})


if __name__ == '__main__':
    unittest.main()
