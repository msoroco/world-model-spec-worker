import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import analysis
import traffic_sweep
import traffic_sweep_audit


def write(path,value):Path(path).write_text(json.dumps(value)+'\n')


class SweepAuditTests(unittest.TestCase):
    def inventory(self,root):
        records=[]
        baseline=json.loads((ROOT/'scene.json').read_text())
        for variant in traffic_sweep.CHANGES:
            for label in ('signaled','unsignaled'):
                attempt=Path(root)/variant/label;attempt.mkdir(parents=True)
                scene=dict(baseline,case_id=ROOT.name+'__'+label+'_left_turn',
                           signal_enabled=label=='signaled')
                write(attempt/'scene.json',scene)
                _,policy,_=traffic_sweep.select(scene,variant)
                write(attempt/'traffic-policy.json',policy)
                zone={'zone_kind':'marked_no_passing_zone','striping_source':'native_map',
                      'stripe_y_m':0,'traffic_sweep_variant_id':variant,
                      'traffic_policy_sha256':traffic_sweep_audit.sha(attempt/'traffic-policy.json'),
                      'authority_source_sha256':'frozen-fixture-authority-hash'}
                write(attempt/'zone-context.json',zone)
                history=[]
                for frame in range(101):
                    time=frame/20
                    y=-2 if frame<50 else .25
                    body=[[0,y-.5,0],[1,y-.5,0],[1,y+.5,0],[0,y+.5,0]]
                    history.append({'frame':frame,'time_s':time,'ego_body_vertices_m':body,
                       'left_signal':label=='signaled',
                       'oncoming_velocity_xy_mps':[policy['oncoming_velocity_x_mps']+.001*frame,0],
                       'following_velocity_xy_mps':[policy['following_velocity_x_mps']-.001*frame,0],
                       'oncoming_body_gap_m':20-frame/100,
                       'following_body_gap_m':15+frame/100,
                       'traffic_command_velocity_x_mps':{
                           'oncoming':policy['oncoming_velocity_x_mps'],
                           'following':policy['following_velocity_x_mps']}})
                (attempt/'turn-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in history))
                sources=('turn-history.jsonl','zone-context.json','traffic-policy.json')
                write(attempt/'acquisition.json',{name:{'kind':'original_native',
                    'sha256':traffic_sweep_audit.sha(attempt/name)} for name in sources})
                write(attempt/'capture-seal.json',{'sources':{
                    name:traffic_sweep_audit.sha(attempt/name) for name in sources}})
                saved=attempt/'saved-result.json'
                write(saved,{'case_id':scene['case_id'],'setup_confirmed':True,
                    'behavior_attempted':True,'maneuver_completed':True,
                    'measured_values':analysis.measure(attempt)})
                records.append({'attempt':str(attempt),'saved_result':str(saved)})
        return records

    def test_complete_paired_sweep_and_missing_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            records=self.inventory(temp)
            result=traffic_sweep_audit.audit(records)
            self.assertTrue(result['passed'])
            self.assertEqual(result['variant_pairs'],9)
            self.assertIsNone(result['legal_verdict'])
            with self.assertRaisesRegex(ValueError,'omits or duplicates'):
                traffic_sweep_audit.audit(records[:-1])

    def test_rejects_stale_source_and_changed_saved_response(self):
        with tempfile.TemporaryDirectory() as temp:
            records=self.inventory(temp)
            attempt=Path(records[0]['attempt'])
            saved=Path(records[0]['saved_result'])
            original=saved.read_text();value=json.loads(original)
            value['measured_values']['traffic_response_window']['participants']['oncoming']['before']['speed_samples_mps'][0]=99
            write(saved,value)
            with self.assertRaisesRegex(ValueError,'saved participant response differs'):
                traffic_sweep_audit.audit(records)
            saved.write_text(original)
            value=json.loads(original)
            value['measured_values']['traffic_response_window']['participants']['following']['minimum_gap_change_m']=99
            write(saved,value)
            with self.assertRaisesRegex(ValueError,'saved response changes differ'):
                traffic_sweep_audit.audit(records)
            saved.write_text(original)
            with (attempt/'turn-history.jsonl').open('a') as stream:stream.write('{}\n')
            with self.assertRaisesRegex(ValueError,'original source missing or stale'):
                traffic_sweep_audit.audit(records)


if __name__=='__main__':unittest.main()
