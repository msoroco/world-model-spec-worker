import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import runner


class ExactBundle(TestCase):
    def test_exact_source_binding(self):
        case, parameters = runner.check()
        self.assertEqual(case, json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())['selected_case_id'])
        self.assertIn(parameters['route_kind'], ('adjacent', 'opposite'))

    def test_original_operator_required(self):
        with patch('sys.argv', ['runner.py', '--output-dir', '.', '--host', '127.0.0.1', '--port', '2000']), patch.dict('os.environ', {'SCENARIO_C111329_ORIGINAL_OPERATOR': '', 'SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256': ''}):
            with self.assertRaisesRegex(ValueError, 'reviewed original C111329'):
                runner.main()
