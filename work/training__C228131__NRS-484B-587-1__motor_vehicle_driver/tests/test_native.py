"""CPU checks of frozen entry requests without CARLA or authority claims."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geometry import check as geometry_check
from route import target
from runner import check


class NativeEntry(unittest.TestCase):
    def test_paved_entry_and_two_crossing_requests(self):
        geometry = geometry_check()
        self.assertTrue(geometry['paved_entrance_crosses_edge'])
        self.assertFalse(geometry['controlled_access_or_official_authority_verified'])
        for mode, crossing in (('witness_1', 0), ('witness_2', 60)):
            self.assertEqual(target(mode, 0)['requested_crossing_x_m'], crossing)
            self.assertLess(target(mode, 0)['y_m'], -3.5)
            self.assertGreater(target(mode, 599)['y_m'], -3.5)

    def test_bundle_check(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertFalse(check(config)['original_physical_or_legal_status_verified'])

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            target('exit_road', 0)


if __name__ == '__main__':
    unittest.main()
