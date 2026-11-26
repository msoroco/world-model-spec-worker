import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import runner
from parked_lamps import CASES
from source_packet import ASSIGNMENT


class RunnerTests(unittest.TestCase):
    def test_selected_case_and_reviewed_packet_gate(self):
        if not (HERE / 'config.json').exists():
            self.skipTest('selected bundle not built')
        config, case = runner.check()
        self.assertEqual(config['selected_case_id'], ASSIGNMENT + '__' + case.name)
        self.assertIn(case.name, {item.name for item in CASES})
        with patch('sys.argv', ['runner.py', '--host', 'localhost', '--port', '2000',
                                '--output-dir', 'attempt']):
            with patch.dict('os.environ', {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'source-hashed reviewed parked-light'):
                    runner.main()
