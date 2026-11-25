import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c179789_source_intake',
                                             ROOT / 'cases/reviewed_source_intake.py')
INTAKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTAKE)


class ReviewedSourceIntakeTests(unittest.TestCase):
    def reviewed_fixture(self):
        construction = json.loads((ROOT / 'construction.json').read_text())
        files = {row['path']: row for row in construction['files']}
        road = json.loads(files['road_packet.json']['content'])
        surface = json.loads(files['surface_packet.json']['content'])
        road.update(review_status='reviewed_native_road_site', reviewer='fixture reviewer',
                    road_review_basis='fixture map waypoint',
                    traffic_review_basis='fixture actor path',
                    camera_review_basis='fixture camera plan', native_map_id='FixtureMap')
        surface.update(review_status='reviewed_native_surface', reviewer='fixture reviewer',
                       review_basis='fixture pavement document', native_map_id='FixtureMap')
        seed = 'Fixture pavement observation\n'
        weather = json.loads(files['weather.json']['content'])
        weather['native_map_id'] = 'FixtureMap'
        weather.pop('status', None)
        weather_text = json.dumps(weather, indent=2) + '\n'
        surface['source'] = {'path': 'surface.txt', 'sha256': INTAKE.sha(seed)}
        road['weather_profile_source'] = {'path': 'weather.json',
                                          'sha256': INTAKE.sha(weather_text)}
        files['surface-seed.txt']['content'] = seed
        files['weather.json']['content'] = weather_text
        files['surface_packet.json']['content'] = json.dumps(surface, indent=2) + '\n'
        files['road_packet.json']['content'] = json.dumps(road, indent=2) + '\n'
        return construction

    def test_structural_source_binding_and_changed_source(self):
        source = self.reviewed_fixture()
        self.assertEqual(INTAKE.validate_case(source)['native_map_id'], 'FixtureMap')
        files = {row['path']: row for row in source['files']}
        files['surface-seed.txt']['content'] = 'changed\n'
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            INTAKE.validate_case(source)

    def test_synthetic_selected_packet_rejected(self):
        source = json.loads((ROOT / 'construction.json').read_text())
        with self.assertRaisesRegex(ValueError, 'review required'):
            INTAKE.validate_case(source)


if __name__ == '__main__':
    unittest.main()
