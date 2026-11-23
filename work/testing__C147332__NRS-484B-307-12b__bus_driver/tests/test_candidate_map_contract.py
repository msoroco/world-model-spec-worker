"""The bus route relies on a straight constant-width two-lane map."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from copy import deepcopy
import xml.etree.ElementTree as ET

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

    def test_extra_road_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'extra-road.xodr'
            root = ET.fromstring(candidate_opendrive())
            other = deepcopy(root.find('road'))
            other.set('id', '999')
            root.append(other)
            ET.ElementTree(root).write(path, encoding='unicode')
            with self.assertRaisesRegex(ValueError, 'exactly one road'):
                check_fixed_map(path)

    def test_extra_lane_section_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'extra-section.xodr'
            root = ET.fromstring(candidate_opendrive())
            lanes = root.find('./road/lanes')
            section = deepcopy(lanes.find('laneSection'))
            section.set('s', '45')
            lanes.append(section)
            ET.ElementTree(root).write(path, encoding='unicode')
            with self.assertRaisesRegex(ValueError, 'exactly one lane section'):
                check_fixed_map(path)


if __name__ == '__main__':
    unittest.main()
