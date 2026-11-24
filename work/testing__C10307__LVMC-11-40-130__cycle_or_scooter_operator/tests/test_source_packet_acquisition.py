import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_packet_acquisition import capture_world_sources, assemble_reviewed_scene

CASE = ROOT.name + '__reference'


class SourcePacketAcquisitionTests(unittest.TestCase):
    def world(self):
        return SimpleNamespace(
            get_map=lambda: SimpleNamespace(name='ReviewedCityMap',
                                            to_opendrive=lambda: '<OpenDRIVE/>\n'),
            get_blueprint_library=lambda: [SimpleNamespace(id=value) for value in
                                           ('vehicle.bicycle', 'static.rack', 'walker.pedestrian.0001')])

    def packets(self, root, observed):
        values = {
            'municipal': {'city_of_las_vegas': True, 'world_map': observed['world_map'],
                          'map_sha256': observed['road_source']['sha256']},
            'bicycle': {'human_powered': True, 'moped': False,
                        'blueprint_id': 'vehicle.bicycle'},
            'rack': {'rack_type': 'bicycle_rack', 'blueprint_id': 'static.rack'},
        }
        paths = {}
        for name, value in values.items():
            path = root / (name + '.json')
            path.write_text(json.dumps({'source_kind': 'reviewed_original',
                                        'reviewed_by': 'CPU test reviewer', **value}))
            paths[name] = path
        return paths

    def test_observe_then_assemble_reviewed_exact_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observed = capture_world_sources(self.world(), root / 'capture')
            self.assertEqual(json.loads((root / 'capture/observation.json').read_text()), observed)
            paths = self.packets(root, observed)
            scene = root / 'scene.json'
            env = assemble_reviewed_scene(observed, CASE, scene, **paths)
            self.assertEqual(env['C10307_SCENE_SOURCE'], str(scene.resolve()))
            self.assertEqual(json.loads(scene.read_text())['map_sha256'],
                             observed['road_source']['sha256'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                capture_world_sources(self.world(), root / 'capture')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                assemble_reviewed_scene(observed, CASE, scene, **paths)

    def test_reject_wrong_map_even_with_reviewed_name_and_clean_failed_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observed = capture_world_sources(self.world(), root / 'capture')
            paths = self.packets(root, observed)
            municipal = json.loads(paths['municipal'].read_text())
            municipal['map_sha256'] = '0' * 64
            paths['municipal'].write_text(json.dumps(municipal))
            scene = root / 'wrong-scene.json'
            with self.assertRaisesRegex(ValueError, 'municipal jurisdiction packet differs'):
                assemble_reviewed_scene(observed, CASE, scene, **paths)
            self.assertFalse(scene.exists())

    def test_near_rack_requires_exact_reviewed_pedestrian(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observed = capture_world_sources(self.world(), root / 'capture')
            paths = self.packets(root, observed)
            near = CASE.replace('__reference', '__pedestrian_near_rack')
            with self.assertRaisesRegex(ValueError, 'pedestrian reviewed packet required'):
                assemble_reviewed_scene(observed, near, root / 'scene.json', **paths)
            pedestrian = root / 'pedestrian.json'
            pedestrian.write_text(json.dumps({
                'source_kind': 'reviewed_original', 'reviewed_by': 'CPU test reviewer',
                'case_id': near, 'blueprint_id': 'walker.pedestrian.0001',
                'rack_blueprint_id': 'static.rack',
                'spawn_pose': {'x': .5, 'y': 3.5, 'z': .2, 'yaw': 90.0}}))
            env = assemble_reviewed_scene(observed, near, root / 'scene.json',
                                          pedestrian=pedestrian, **paths)
            self.assertTrue(env['C10307_SCENE_SHA256'])

    def test_reject_reviewed_blueprint_absent_from_observed_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observed = capture_world_sources(self.world(), root / 'capture')
            paths = self.packets(root, observed)
            bicycle = json.loads(paths['bicycle'].read_text())
            bicycle['blueprint_id'] = 'vehicle.unobserved_bicycle'
            paths['bicycle'].write_text(json.dumps(bicycle))
            scene = root / 'unobserved-scene.json'
            with self.assertRaisesRegex(ValueError, 'blueprint inventory differs'):
                assemble_reviewed_scene(observed, CASE, scene, **paths)
            self.assertFalse(scene.exists())


if __name__ == '__main__':
    unittest.main()
