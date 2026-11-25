"""CPU checks for the two source-defined right-turn lane designs."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive
from finalize import independent_lane_review


class SelectedBranches(unittest.TestCase):
    def test_qualifying_right_only_design_has_turn_connector(self):
        map_root = ET.fromstring(open_drive(True))
        self.assertIsNotNone(map_root.find("road[@id='1']/objects/object[@name='right_turn_arrow']"))
        self.assertIsNone(map_root.find("road[@id='14']"))
        self.assertEqual([c.attrib['connectingRoad'] for c in map_root.findall('junction/connection')], ['13'])

    def test_extreme_right_design_has_real_through_option(self):
        map_root = ET.fromstring(open_drive(False))
        self.assertIsNone(map_root.find("road[@id='1']/objects/object"))
        connectors = {c.attrib['connectingRoad']: c.find('laneLink').attrib
                      for c in map_root.findall('junction/connection')}
        self.assertEqual(connectors, {'13': {'from': '-2', 'to': '-2'},
                                      '14': {'from': '-2', 'to': '-2'}})
        through = map_root.find("road[@id='14']")
        self.assertEqual(through.find('link/successor').attrib['elementId'], '2')
        self.assertIsNotNone(through.find('planView/geometry/line'))

    def test_original_review_cannot_be_inferred_from_synthetic_source(self):
        for suffix in ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2'):
            folder = HERE / 'selected-v2-source' / suffix
            config = json.loads((folder / 'config.json').read_text())
            self.assertFalse(independent_lane_review(folder, config['case_id'],
                            'qualifying_right_only_lane' if suffix.startswith('witness_')
                            else 'alternative_extreme_right_lane', 480))


if __name__ == '__main__':
    unittest.main()
