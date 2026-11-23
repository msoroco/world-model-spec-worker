"""The bus route relies on a straight constant-width two-lane map."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_construction import candidate_opendrive
from candidate_map_contract import check_fixed_map


class CandidateMapContractTests(unittest.TestCase):
    def check_changed(self, before, after, message):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'changed.xodr'
            path.write_text(candidate_opendrive().replace(before, after, 1))
            with self.assertRaisesRegex(ValueError, message):
                check_fixed_map(path)

    def test_current_map_passes(self):
        result = check_fixed_map(ROOT / 'candidate-red-x-road.xodr')
        self.assertEqual(result['lane_ids'], [-1, -2])

    def test_varying_width_rejected(self):
        self.check_changed('a="3.6" b="0"', 'a="3.6" b="0.1"', 'lane width')

    def test_shifted_lane_offset_rejected(self):
        self.check_changed('laneOffset s="0" a="0"', 'laneOffset s="0" a="1"', 'lane offset')

    def test_changed_straight_geometry_rejected(self):
        self.check_changed('hdg="0" length="90"', 'hdg="0.1" length="90"',
                           'straight route geometry')


if __name__ == '__main__':
    unittest.main()
