import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / 'source_comparison_audit.py'
spec = importlib.util.spec_from_file_location('source_comparison_audit', MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def item(suffix, speed, interest='person', offset=1.8):
    config = {key: 'same' for key in module.FIXED}
    config.update({'selected_case_id': module.PREFIX + suffix,
                   'target_speed_mps': speed, 'protected_interest': interest,
                   'pedestrian_offset_m': offset})
    observed = {'source_sha256': {name: 'a' * 64 for name in module.SOURCES},
                'maximum_observed_speed_mps': speed,
                'minimum_pedestrian_gap_m': 1.0,
                'minimum_property_gap_m': 2.0}
    return {'config': config, 'observed': observed, 'report_sha256': 'b' * 64}


class SourceComparisonAuditTest(unittest.TestCase):
    def test_speed_comparison_fixed_and_difference(self):
        rows = [item(f'person_{speed}mps', speed) for speed in (3, 5, 7)]
        with patch.object(module, 'read_saved', side_effect=rows):
            result = module.audit('person_speed_sweep', ['a', 'b', 'c'])
        self.assertTrue(result['comparison_complete'])
        self.assertEqual(result['requested_values'], [3, 5, 7])

    def test_fixed_polygon_change_rejected(self):
        rows = [item(f'person_{speed}mps', speed) for speed in (3, 5, 7)]
        rows[1]['config']['alley_polygon_source'] = 'changed'
        with patch.object(module, 'read_saved', side_effect=rows):
            with self.assertRaisesRegex(ValueError, 'fixed condition differs'):
                module.audit('person_speed_sweep', ['a', 'b', 'c'])

    def test_wrong_deliberate_speed_rejected(self):
        rows = [item(f'person_{speed}mps', speed) for speed in (3, 5, 7)]
        rows[1]['config']['target_speed_mps'] = 3
        with patch.object(module, 'read_saved', side_effect=rows):
            with self.assertRaisesRegex(ValueError, 'deliberate variable did not differ'):
                module.audit('person_speed_sweep', ['a', 'b', 'c'])

    def test_original_source_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case_id = module.PREFIX + 'person_3mps'
            for name in module.SOURCES:
                (root / name).write_text('{}\n')
            (root / 'polygon.json').write_text('{}\n')
            config = {'selected_case_id': case_id,
                      'alley_polygon_source': {'path': 'polygon.json',
                                               'sha256': module.digest(root / 'polygon.json')}}
            (root / 'config.json').write_text(json.dumps(config))
            (root / 'analysis-report.json').write_text(json.dumps({
                'case_id': case_id, 'measurements': {'alley_original_exposure': {'value': {
                    'source_sha256': {name: '0' * 64 for name in module.SOURCES}}}}}))
            with self.assertRaisesRegex(ValueError, 'original source hash differs'):
                module.read_saved(root)


if __name__ == '__main__':
    unittest.main()
