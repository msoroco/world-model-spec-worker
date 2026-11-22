import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from judgment_sweep import participants,run,signal
from runner import control_step,load_scene


class JudgmentSweepTests(unittest.TestCase):
    def test_exhibition_timing_and_each_occupant_role(self):
        proof=run()
        profiles=proof['profiles']
        self.assertEqual([row['profile'] for row in profiles],
                         ['before_entry','during_occupancy','vehicle_only',
                          'pedestrian_only','after_clearance'])
        self.assertEqual([row['hold_at_stop_line'] for row in profiles],
                         [False,True,True,True,False])
        self.assertGreater(profiles[1]['nominal_clearance_frame'],
                           profiles[1]['exhibition_frame'])
        self.assertEqual([row['nominal_participants'][0]['role'] for row in profiles[2:4]],
                         ['vehicle','pedestrian'])
        self.assertTrue(all(row['legal_verdict'] is None for row in profiles))
        self.assertIsNone(proof['physical_result'])
        self.assertEqual(len({row['case_id'] for row in profiles}),1)

    def test_missing_independent_lawful_source_stays_on_hold(self):
        scene={**load_scene(),'participant_occupancy_setup':'lawfully_present'}
        people=participants(scene,5)
        people[0]['lawful_presence_source']=None
        decision=control_step(scene,signal(100),people,
                              [[-12,-.5,0],[-11,-.5,0],[-11,.5,0],[-12,.5,0]])
        self.assertEqual(decision['reason'],'unverified_exhibition_lawfulness')
        self.assertEqual(decision['control']['brake'],1.0)


if __name__=='__main__':unittest.main()
