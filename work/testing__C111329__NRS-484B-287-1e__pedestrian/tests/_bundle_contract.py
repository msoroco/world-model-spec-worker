import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import runner

class ExactBundle(TestCase):
    def test_case_and_four_camera_source_contract(self):
        config = runner.check()
        self.assertEqual(config['selected_case_id'], json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())['selected_case_id'])
        self.assertEqual(config['duration_s'], 45)
        self.assertEqual(len(config['cameras']), 4)

    def test_original_operator_is_required(self):
        with patch.dict('os.environ', {'SCENARIO_C111329_ORIGINAL_OPERATOR': '',
                                      'SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256': ''}):
            with self.assertRaisesRegex(ValueError, 'source-reviewed C111329 Native operator'):
                runner._operator()
