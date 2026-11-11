from pathlib import Path
import sys
import json
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_headlamp_probe import CASE_ID, check_config, prepare_output


class NativeProbeTests(unittest.TestCase):
    def test_exact_probe_config(self):
        config = {'selected_case_id': CASE_ID, 'law_id': 'NRS-484D-215-2',
                  'cell_id': 'C178038', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 80, 'requested_gap_ft': 299,
                  'requested_uppermost_distribution': True,
                  'construction_probe_only': True}
        check_config(config)
        for change in ({'requested_gap_ft': 300}, {'construction_probe_only': False},
                       {'selected_case_id': CASE_ID.replace('299', '301')},
                       {'requested_uppermost_distribution': False}):
            wrong = {**config, **change}
            with self.assertRaises(ValueError):
                check_config(wrong)

    def test_compared_case_requires_its_beam_and_gap(self):
        base = {'selected_case_id': CASE_ID.replace('upper', 'other'),
                'law_id': 'NRS-484D-215-2', 'cell_id': 'C178038',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 80,
                'requested_gap_ft': 299, 'requested_uppermost_distribution': False,
                'construction_probe_only': True}
        check_config(base)
        for wrong in ({**base, 'requested_uppermost_distribution': True},
                      {**base, 'selected_case_id': CASE_ID.replace('299', '300')},
                      {**base, 'selected_case_id': CASE_ID.replace('299', '301')}):
            with self.assertRaises(ValueError):
                check_config(wrong)
        for gap in (300, 301):
            check_config({**base, 'selected_case_id': CASE_ID.replace('299', str(gap)).replace('other', 'upper'),
                          'requested_gap_ft': gap, 'requested_uppermost_distribution': True})

    def test_runtime_materialized_output_and_prior_acquisition(self):
        config = {'selected_case_id': CASE_ID, 'law_id': 'NRS-484D-215-2',
                  'cell_id': 'C178038', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 80, 'requested_gap_ft': 299,
                  'requested_uppermost_distribution': True,
                  'construction_probe_only': True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'attempt'
            root.mkdir()
            (root / 'construction.json').write_text('{}')
            (root / 'config.json').write_text(json.dumps(config))
            self.assertEqual(prepare_output(root, config), root)
            self.assertEqual(json.loads((root / 'config.json').read_text()), config)
            (root / 'trace.jsonl').write_text('original\n')
            with self.assertRaisesRegex(ValueError, 'prior Native acquisition'):
                prepare_output(root, config)
            self.assertEqual((root / 'trace.jsonl').read_text(), 'original\n')
            (root / 'trace.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'config differs'):
                prepare_output(root, {**config, 'requested_gap_ft': 300})


if __name__ == '__main__':
    unittest.main()
