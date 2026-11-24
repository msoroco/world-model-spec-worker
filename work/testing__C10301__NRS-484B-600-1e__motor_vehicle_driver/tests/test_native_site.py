import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_site import construct

CASE = ROOT.name + '__above'
CAMERAS = ('front', 'front_left', 'front_right', 'rear')


class Spawned:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class FakeMap:
    name = 'diagnostic-original-map'

    def __init__(self):
        self.wrong_lane_at = None
        self.centerline_offset = 0

    def to_opendrive(self):
        return '<OpenDRIVE diagnostic="true"/>'

    def get_waypoint(self, location):
        return SimpleNamespace(road_id=1,
                               lane_id=-2 if location.x == self.wrong_lane_at else -1,
                               transform=SimpleNamespace(location=SimpleNamespace(
                                   x=location.x, y=self.centerline_offset, z=0)))


class FakeWorld:
    def __init__(self):
        self.map = FakeMap()
        self.spawned = []
        self.fail_at = None

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: FakeBlueprint(name))

    def spawn_actor(self, blueprint, transform, attach_to=None):
        if len(self.spawned) == self.fail_at:
            return None
        actor = Spawned()
        actor.blueprint = blueprint
        self.spawned.append(actor)
        return actor


class FakeBlueprint:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


def transform(spec):
    return SimpleNamespace(location=SimpleNamespace(x=spec.get('x_m', 0)))


class NativeSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'site.json'
        self.world = FakeWorld()
        self.packet = {
            'format': 'c10301-native-site-v1', 'case_id': CASE,
            'cell_id': 'C10301', 'layout': 'alley', 'control': 'access_aisle',
            'actor': 'motor_vehicle_driver', 'maneuver': 'travel',
            'diagnostic_fixture': True,
            'map_name': self.world.map.name,
            'opendrive_sha256': hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest(),
            'access_aisle_source_ref': 'diagnostic aisle',
            'route_source_ref': 'diagnostic route',
            'route': [{'s_m': i * 10, 'x_m': i * 10,
                       'y_m': 0, 'z_m': 0} for i in range(181)],
            'vehicle_blueprint_id': 'vehicle.diagnostic',
            'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                               'x_m': 0, 'y_m': 0, 'z_m': 1.5,
                               'pitch_deg': 0, 'yaw_deg': 0, 'roll_deg': 0}
                        for name in CAMERAS},
        }

    def save(self):
        self.path.write_text(json.dumps(self.packet) + '\n')

    def test_constructs_exact_actor_and_four_cameras_with_source_hash(self):
        self.save()
        site = construct(self.world, self.path, CASE, transform)
        self.assertEqual(len(site.cameras), 4)
        self.assertEqual(site.packet_sha256, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(len(self.world.spawned), 5)
        self.assertEqual(self.world.spawned[1].blueprint.attributes,
                         {'image_size_x': '1920', 'image_size_y': '1080',
                          'sensor_tick': '0.05'})
        self.assertEqual(self.world.spawned[2].blueprint.attributes['image_size_x'],
                         '1280')
        site.close()
        self.assertTrue(all(item.destroyed for item in self.world.spawned))

    def test_short_or_wrong_lane_route_rejected_before_spawn(self):
        self.packet['route'] = self.packet['route'][:100]
        self.save()
        with self.assertRaisesRegex(ValueError, 'too short'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(self.world.spawned, [])
        self.packet['route'] = [{'s_m': i * 10, 'x_m': i * 10,
                                 'y_m': 0, 'z_m': 0} for i in range(181)]
        self.world.map.wrong_lane_at = 500
        self.save()
        with self.assertRaisesRegex(ValueError, 'leaves reviewed lane'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(self.world.spawned, [])

    def test_failed_sensor_spawn_destroys_original_actor_and_sensors(self):
        self.world.fail_at = 3
        self.save()
        with self.assertRaisesRegex(ValueError, 'camera spawn failed'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(len(self.world.spawned), 3)
        self.assertTrue(all(item.destroyed for item in self.world.spawned))

    def test_map_hash_and_case_identity_prevent_spawn(self):
        self.packet['opendrive_sha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'map source differs'):
            construct(self.world, self.path, CASE, transform)
        self.packet['opendrive_sha256'] = hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest()
        self.packet['case_id'] = ROOT.name + '__equal'
        self.save()
        with self.assertRaisesRegex(ValueError, 'identity'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(self.world.spawned, [])

    def test_production_site_requires_bound_route_and_aisle_files(self):
        route = self.path.parent / 'route-source.json'
        aisle = self.path.parent / 'aisle-source.json'
        route.write_text('route source\n')
        aisle.write_text('aisle source\n')
        self.packet['diagnostic_fixture'] = False
        self.packet['route_source_ref'] = {
            'path': route.name, 'sha256': hashlib.sha256(route.read_bytes()).hexdigest()}
        self.packet['access_aisle_source_ref'] = {
            'path': aisle.name, 'sha256': hashlib.sha256(aisle.read_bytes()).hexdigest()}
        self.save()
        site = construct(self.world, self.path, CASE, transform)
        site.close()
        self.world.spawned.clear()
        aisle.write_text('changed aisle source\n')
        with self.assertRaisesRegex(ValueError, 'source SHA-256 differs'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(self.world.spawned, [])

    def test_route_coordinates_must_match_loaded_map_centerline(self):
        self.world.map.centerline_offset = 20
        self.save()
        with self.assertRaisesRegex(ValueError, 'loaded-map centerline'):
            construct(self.world, self.path, CASE, transform)
        self.assertEqual(self.world.spawned, [])

    def test_actual_actor_route_readback_rejects_offset_lane_and_reverse(self):
        self.save()
        site = construct(self.world, self.path, CASE, transform)
        def actor(x, y=0):
            return SimpleNamespace(get_transform=lambda: SimpleNamespace(
                location=SimpleNamespace(x=x, y=y, z=0)))
        self.assertAlmostEqual(site.observe_route(actor(101.5))['route_s_m'], 101.5)
        self.assertAlmostEqual(site.observe_route(actor(110, 1.5))['centerline_offset_m'], 1.5)
        with self.assertRaisesRegex(ValueError, 'centerline'):
            site.observe_route(actor(120, 3))
        self.world.map.wrong_lane_at = 120
        with self.assertRaisesRegex(ValueError, 'reviewed route lane'):
            site.observe_route(actor(120))
        self.world.map.wrong_lane_at = None
        with self.assertRaisesRegex(ValueError, 'reversed'):
            site.observe_route(actor(100))
        site.close()


if __name__ == '__main__':
    unittest.main()
