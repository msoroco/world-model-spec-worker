"""Three-outcome CPU proof for the case-specific sampled U-turn criterion."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO/'.runtime-work/c10808-physical-test'))
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical


class PhysicalTurnTests(unittest.TestCase):
    def make(self,root,turn=True):
        config=json.loads((ROOT/'config.json').read_text())
        config['duration_s']=.45
        (root/'config.json').write_text(json.dumps(config))
        phases=[];trace=[];mapping=[]
        for i in range(9):
            frame=100+i;time_s=(i+1)/20
            x=float(i);yaw=180.*i/8 if turn else 0.
            body=[[x-.2,-.2,0.],[x-.2,.2,0.],
                  [x+.2,-.2,0.],[x+.2,.2,0.]]
            phases.append({'frame':frame,'time_s':time_s,
                           'operator_body_vertices_m':body,'heading_deg':yaw})
            trace.append({'frame':frame,'time_s':time_s,'position_m':[x,0.,0.],
                          'heading_deg':yaw})
            mapping.append({'video_frame':i,'carla_frame':frame,'time_s':time_s})
        for name,rows in [('phase-events.jsonl',phases),('trace.jsonl',trace),
                          ('video_frames.jsonl',mapping)]:
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return config

    def test_turn_met_not_met_and_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=self.make(root,True)
            checks=assess_physical(root,config,[{'matched':True}])['physical_checks']
            self.assertEqual({key:checks[key]['status'] for key in
                              ('setup','target','maneuver')},
                             {'setup':'met','target':'met','maneuver':'met'})
            config=self.make(root,False)
            checks=assess_physical(root,config,[{'matched':True}])['physical_checks']
            self.assertEqual(checks['maneuver']['status'],'not_met')
            (root/'phase-events.jsonl').unlink()
            checks=assess_physical(root,config,[{'matched':True}])['physical_checks']
            self.assertEqual(checks['maneuver']['status'],'unverified')


if __name__=='__main__':unittest.main()
