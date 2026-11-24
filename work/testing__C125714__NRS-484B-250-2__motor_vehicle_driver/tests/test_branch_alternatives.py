"""Reviewed statutory alternatives and original-control CPU packets."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from branch_alternatives import observe_brake, observe_context, sha


class AlternativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.road = self.root/'road.xodr'
        self.road.write_text('original map for CPU test\n')
        self.site = self.root/'site-context.json'
        self.reviewed = self.root/'reviewed-context.json'
        self.case = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__device_controlled'
        self.fields = {'case_id':self.case,'map_sha256':sha(self.road),
                       'ego_highway':'A','other_highway':'B','ego_side':'left',
                       'other_side':'right','approach_relation':'crossing',
                       'official_device_controls_intersection':True,
                       'other_left_turn_intent':False,'other_left_turn_making':False,
                       'subsection_4_context_reviewed':True}
        self.write_context()

    def write_context(self):
        self.site.write_text(json.dumps(self.fields)+'\n')
        self.reviewed.write_text(json.dumps(dict(self.fields,reviewer='CPU test'))+'\n')

    def test_device_and_opposite_turn_are_separate_source_facts(self):
        result = observe_context(self.site,self.road,self.reviewed)
        self.assertTrue(result['facts']['official_device_controlled'])
        self.assertTrue(result['facts']['different_highways_left_right'])
        self.assertEqual(result['legal_exception_applies'],'unresolved')
        self.fields.update(approach_relation='opposite',ego_highway='A',
                           other_highway='A',official_device_controls_intersection=False,
                           other_left_turn_intent=True,other_left_turn_making=True)
        self.write_context()
        turn = observe_context(self.site,self.road,self.reviewed)
        self.assertTrue(turn['facts']['opposite_intends_left'])
        self.assertTrue(turn['facts']['opposite_makes_left'])
        self.assertFalse(turn['facts']['different_highways_left_right'])

    def test_changed_review_and_impossible_turn_rejected(self):
        self.fields['other_left_turn_making'] = True
        self.write_context()
        with self.assertRaisesRegex(ValueError,'making requires'):
            observe_context(self.site,self.road,self.reviewed)
        self.fields['other_left_turn_making'] = False
        self.write_context()
        edited = json.loads(self.reviewed.read_text())
        edited['official_device_controls_intersection'] = False
        self.reviewed.write_text(json.dumps(edited))
        with self.assertRaisesRegex(ValueError,'differs from reviewed'):
            observe_context(self.site,self.road,self.reviewed)

    def test_original_control_join_and_no_legal_yield_claim(self):
        mapping = [{'video_frame':i,'carla_frame':100+i,'time_s':i*.05}
                   for i in range(3)]
        control = [{'frame':m['carla_frame'],'time_s':m['time_s'],
                    'ego_brake':b} for m,b in zip(mapping,(0,.5,0))]
        mp,cp = self.root/'video_frames.jsonl',self.root/'controller-history.jsonl'
        mp.write_text(''.join(json.dumps(row)+'\n' for row in mapping))
        cp.write_text(''.join(json.dumps(row)+'\n' for row in control))
        result = observe_brake(cp,mp,.1)
        self.assertTrue(result['ego_brake_observed_before_other_entry'])
        self.assertEqual(result['right_of_way_yielding'],'unresolved')
        control[1]['frame'] += 1
        cp.write_text(''.join(json.dumps(row)+'\n' for row in control))
        with self.assertRaisesRegex(ValueError,'identity changed'):
            observe_brake(cp,mp,.1)


if __name__ == '__main__':
    unittest.main()
