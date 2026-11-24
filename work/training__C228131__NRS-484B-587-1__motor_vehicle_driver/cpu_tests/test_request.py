import json
from pathlib import Path
import unittest

from cpu_runner import check
from entry_cpu import requested_pose


class RequestedEntry(unittest.TestCase):
    def test_current_case(self):
        config = json.loads(Path('config.json').read_text())
        result = check()
        self.assertEqual(result['case_id'], config['case_id'])
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['native_executed'])

    def test_entry_variable_and_duration(self):
        self.assertEqual(requested_pose('witness_1', 220)['center_xy_m'][0], 0)
        self.assertEqual(requested_pose('witness_2', 220)['center_xy_m'][0], 60)
        self.assertEqual(requested_pose('witness_1', 599)['time_s'], 599 / 20)
