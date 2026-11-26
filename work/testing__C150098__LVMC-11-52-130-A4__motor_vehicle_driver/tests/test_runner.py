"""Exact materialized hydrant bundle identity checks."""
import json
import unittest

from hydrant import ASSIGNMENT
from runner import check
from test_native_packet import PacketTest


class RunnerTest(unittest.TestCase):
    setUp = PacketTest.setUp
    save = PacketTest.save

    def config(self):
        return {'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-52-130-A4',
                'cell_id': 'C150098', 'actor': 'motor_vehicle_driver',
                'selected_case_id': ASSIGNMENT + '__upstream_inside',
                'rate_hz': 20, 'duration_s': 45, 'frame_count': 900,
                'required_atoms': [], 'source_packets': [],
                'requested_side': 'upstream', 'requested_gap_m': 4.422,
                'requested_activity': 'park', 'requested_exception': 'none'}

    def test_exact_config(self):
        (self.root / 'config.json').write_text(json.dumps(self.config()), encoding='utf-8')
        self.assertEqual(check(self.root), ASSIGNMENT + '__upstream_inside')

    def test_wrong_case_target_rejected(self):
        config = self.config()
        config['requested_gap_m'] = 4.572
        (self.root / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'exact hydrant construction differs'):
            check(self.root)


if __name__ == '__main__':
    unittest.main()
