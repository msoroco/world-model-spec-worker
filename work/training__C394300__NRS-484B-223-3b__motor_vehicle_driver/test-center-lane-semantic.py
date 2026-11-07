import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('semantic', HERE/'prove-center-lane-semantic.py')
semantic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semantic)
geo_spec = importlib.util.spec_from_file_location('geometry', HERE/'native/geometry.py')
geometry = importlib.util.module_from_spec(geo_spec)
geo_spec.loader.exec_module(geometry)


class CenterLaneSemanticTest(unittest.TestCase):
    def setUp(self):
        self.source = geometry.open_drive()

    def mutate(self, change):
        root = ET.fromstring(self.source)
        lane = root.find("./road[@id='1']/lanes/laneSection/right/lane[@id='-1']")
        change(lane)
        return ET.tostring(root, encoding='unicode')

    def test_source_region_and_core_positive(self):
        region = semantic.source_region(self.source)
        self.assertEqual(region['native_lane_type'], 'bidirectional')
        self.assertEqual(region['authored_use'], 'left_turn_only_both_directions')
        scenes = {'scenes': [{'structures': [{'kind': 'lane', 'boundary': region['boundary']}]}]}
        self.assertTrue(semantic.check_converted(region, scenes)['core_semantics_passed'])

    def test_core_omission_is_not_semantic_pass(self):
        region = semantic.source_region(self.source)
        result = semantic.check_converted(region, {'scenes': [{'structures': []}]})
        self.assertTrue(result['source_semantics_checked'])
        self.assertFalse(result['core_semantics_passed'])

    def test_driving_lane_rejected(self):
        source = self.mutate(lambda lane: lane.set('type', 'driving'))
        with self.assertRaisesRegex(ValueError, 'Bidirectional center lane absent'):
            semantic.source_region(source)

    def test_missing_turn_only_use_rejected(self):
        source = self.mutate(lambda lane: lane.find('userData').set('value', 'general_travel'))
        with self.assertRaisesRegex(ValueError, 'Turn-only bidirectional lane designation absent'):
            semantic.source_region(source)

    def test_variable_width_rejected(self):
        source = self.mutate(lambda lane: lane.find('width').set('b', '.1'))
        with self.assertRaisesRegex(ValueError, 'width profile changed'):
            semantic.source_region(source)


if __name__ == '__main__':
    unittest.main()
