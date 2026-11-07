"""Positive and negative CPU checks for the three source center-lane regions."""
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('semantic',HERE/'prove-center-lane-semantic.py')
semantic=importlib.util.module_from_spec(spec);spec.loader.exec_module(semantic)


class CenterLaneSemanticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(HERE/'draft-construction/scene.xodr').read_text()
        cls.regions=semantic.source_regions(cls.source)

    def test_authored_three_segments(self):
        self.assertEqual([r['road_id'] for r in self.regions],[1,14,2])
        self.assertTrue(all(r['area_m2']>0 for r in self.regions))

    def test_positive_core_regions(self):
        scene={'structures':[{'kind':'lane','boundary':r['boundary']} for r in self.regions]}
        self.assertTrue(semantic.check_converted(self.regions,{'scenes':[scene,scene]})['core_semantics_passed'])

    def test_missing_core_segment(self):
        scene={'structures':[{'kind':'lane','boundary':self.regions[0]['boundary']}]}
        self.assertFalse(semantic.check_converted(self.regions,{'scenes':[scene]})['core_semantics_passed'])

    def test_plain_driving_lane_rejected(self):
        changed=self.source.replace('type="bidirectional"','type="driving"',1)
        with self.assertRaisesRegex(ValueError,'Bidirectional center lane absent'):
            semantic.source_regions(changed)

    def test_changed_turn_only_use_rejected(self):
        changed=self.source.replace('left_turn_only_both_directions','general_use',1)
        with self.assertRaisesRegex(ValueError,'Turn-only bidirectional lane designation absent'):
            semantic.source_regions(changed)


if __name__=='__main__':unittest.main()
