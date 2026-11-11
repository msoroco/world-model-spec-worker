from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import CASE_ID, _longitudinal, check_config, prepare_output
import json
import tempfile


class NativeProbeTests(unittest.TestCase):
    def test_exact_probe_config_and_body_clearance(self):
        config = {'selected_case_id': CASE_ID, 'law_id': 'NRS-484B-207-1',
                  'cell_id': 'C110161', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 160,
                  'requested_return_clearance_m': 3,
                  'duration_s': 8, 'supported_case_ids': [CASE_ID]}
        check_config(config)
        with self.assertRaisesRegex(ValueError, 'marker'):
            check_config({**config, 'construction_probe_only': True})
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            check_config({**config, 'selected_case_id': CASE_ID.replace('wide', 'narrow')})
        row = {'road_tangent_xy': [1, 0],
               'ego_corners': [[19, 2], [21, 2], [21, 4], [19, 4]],
               'other_corners': [[9, -1], [11, -1], [11, 1], [9, 1]]}
        rear, front, abreast = _longitudinal(row)
        self.assertEqual((rear, front, abreast), (19, 11, False))
        row['ego_corners'] = [[9, 2], [11, 2], [11, 4], [9, 4]]
        self.assertTrue(_longitudinal(row)[2])
        row['ego_corners'] = [[9, 0], [11, 0], [11, 2], [9, 2]]
        self.assertFalse(_longitudinal(row)[2])
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            output = Path(directory)
            (output / 'config.json').write_text(json.dumps(config))
            self.assertEqual(prepare_output(config, output), output)
            (output / 'trace.jsonl').write_text('prior Native source\n')
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                prepare_output(config, output)


if __name__ == '__main__':
    unittest.main()
