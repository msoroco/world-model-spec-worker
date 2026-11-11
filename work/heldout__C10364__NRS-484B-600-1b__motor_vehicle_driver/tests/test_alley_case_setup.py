from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alley_case_setup import CASES, PREFIX, case_settings, verify_polygon_source
from native_alley_cases import check_config


class ExactCaseSetupTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        source = self.root / 'alley-polygon-source.json'
        source.write_text(json.dumps({'polygon_xy': [[0,-3],[40,-3],[40,3],[0,3]]}) + '\n')
        self.config = {'law_id': 'NRS-484B-600-1b', 'cell_id': 'C10364',
            'actor': 'motor_vehicle_driver', 'selected_case_id': PREFIX + 'person_3mps',
            'protected_interest': 'person', 'target_speed_mps': 3.0,
            'rate_hz': 20, 'frames': 160, 'duration_s': 8,
            'construction_probe_only': True, 'alley_direction': 'east',
            'alley_polygon_xy': [[0,-3],[40,-3],[40,3],[0,3]],
            'alley_width_m': 6.0,
            'alley_polygon_source': {'path': source.name,
                                     'sha256': sha256(source.read_bytes()).hexdigest()}}

    def test_six_exact_cases_and_hashed_polygon_source(self):
        self.assertEqual(len(CASES), 6)
        for suffix, (interest, speed) in CASES.items():
            config = dict(self.config, selected_case_id=PREFIX + suffix,
                          protected_interest=interest, target_speed_mps=speed)
            settings = check_config(config)
            self.assertEqual(settings['speed_mps'], speed)
            self.assertEqual(verify_polygon_source(settings, self.root).name,
                             'alley-polygon-source.json')

    def test_changed_source_and_wrong_case_rejected(self):
        settings = case_settings(self.config)
        (self.root / 'alley-polygon-source.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            verify_polygon_source(settings, self.root)
        source = self.root / 'alley-polygon-source.json'
        source.write_text(json.dumps({'polygon_xy': [[0,0],[1,0],[1,1],[0,1]]}))
        changed = dict(settings, polygon_source={'path': source.name,
                          'sha256': sha256(source.read_bytes()).hexdigest()})
        with self.assertRaisesRegex(ValueError, 'differs from its source'):
            verify_polygon_source(changed, self.root)
        with self.assertRaisesRegex(ValueError, 'interest'):
            case_settings(dict(self.config, target_speed_mps=7.0))
        with self.assertRaisesRegex(ValueError, 'inside the attempt'):
            case_settings(dict(self.config, alley_polygon_source={
                'path': '../frozen.json', 'sha256': '0'*64}))


if __name__ == '__main__':
    unittest.main()
