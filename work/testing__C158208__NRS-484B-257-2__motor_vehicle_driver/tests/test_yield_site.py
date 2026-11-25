"""CPU source and cleanup checks for the selected yield intersection."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from yield_site import create, validate_site


SOURCE_NAMES = ('map_opendrive', 'jurisdiction', 'intersection_geometry',
                'non_through_classification',
                'all_entrance_controls', 'ego_yield_sign', 'stop_reference',
                'ego_route', 'ego_vehicle', 'other_route', 'other_obligation',
                'through_vehicle_exemption', 'sightlines',
                'officer_control', 'signal_control')


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_second=False):
        self.actors = []
        self.fail_second = fail_second

    def get_blueprint_library(self):
        return self

    def find(self, name):
        return name

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.actors:
            return None
        actor = Actor()
        self.actors.append(actor)
        return actor


class YieldSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        sources = {}
        for name in SOURCE_NAMES:
            path = root / (name + '.txt')
            path.write_text('diagnostic-only ' + name + '\n')
            sources[name] = {'path': str(path),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        spec = lambda x: {'blueprint_id': 'vehicle.test', 'source_citation': 'fixture',
                          'route_source_citation': 'fixture',
                          'location_xyz_m': [x, 0, 0],
                          'rotation_rpy_deg': [0, 0, 0],
                          'route_points_xyz_m': [[x, 0, 0], [x + 10, 0, 0]],
                          'initial_station_m': x}
        self.packet = {
            'format': 'c158208-reviewed-native-site-v1', 'cell_id': 'C158208',
            'law_id': 'NRS-484B-257-2', 'actor': 'motor_vehicle_driver',
            'case_id': 'occupied_response', 'sources': sources,
            'non_through_highway': True, 'ego_yield_sign_present': True,
            'other_obligated_to_stop_or_yield': False,
            'officer_controls': False, 'signal_controls': False,
            'entrances': [{'id': 'west', 'control': 'yield', 'reviewed_source': 'fixture'},
                          {'id': 'north', 'control': 'none', 'reviewed_source': 'fixture'}],
            'ego_entrance_id': 'west', 'other_entrance_id': 'north',
            'stop_reference_station_m': 0, 'intersection_entry_station_m': 4,
            'intersection_polygon_source': 'fixture',
            'ego_route_continuity_review': True, 'other_route_continuity_review': True,
            'spawn_plan': {'ego': spec(-8), 'other': spec(1)}}
        self.path = root / 'site.json'
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.packet) + '\n')

    def test_exact_source_gated_site(self):
        self.assertEqual(validate_site(self.path, 'occupied_response')['cell_id'], 'C158208')
        self.assertEqual(len(create(World(), self.path, lambda p, r: (p, r),
                                    'occupied_response').owned), 2)

    def test_missing_or_changed_source_rejected(self):
        Path(self.packet['sources']['map_opendrive']['path']).write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source absent or changed'):
            validate_site(self.path, 'occupied_response')

    def test_false_obligation_and_missing_control_rejected(self):
        self.packet['entrances'][1]['control'] = 'yield'
        self.save()
        with self.assertRaisesRegex(ValueError, 'obligation mismatch'):
            validate_site(self.path, 'occupied_response')

    def test_partial_native_spawn_releases_owned_actor(self):
        world = World(fail_second=True)
        with self.assertRaisesRegex(ValueError, 'other spawn failed'):
            create(world, self.path, lambda p, r: (p, r), 'occupied_response')
        self.assertTrue(world.actors[0].destroyed)

    def test_close_releases_both_owned_actors(self):
        world = World()
        actors = create(world, self.path, lambda p, r: (p, r), 'occupied_response')
        actors.close()
        self.assertEqual(actors.owned, [])
        self.assertTrue(all(a.destroyed for a in world.actors))


if __name__ == '__main__':
    unittest.main()
