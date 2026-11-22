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
import zone_source


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
                authority=b'synthetic authority review fixture\n'
                (attempt/'zone-authority-source.txt').write_bytes(authority)
                review={'format':'worker-zone-review-source-v1','reviewer':'CPU fixture',
                        'review_method':'source/map join fixture','authority_citation':'fixture',
                        'authority_source_sha256':zone_source.sha_bytes(authority),
                        'designation':'official_no_passing_zone',
                        'destination_kind':'other_left_turn',
                        'subsections_3_and_4_reviewed':True,
                        'road_id':1,'lane_id':-1,'zone_x_limits_m':[-10,10]}
                write(attempt/'zone-review-source.json',review)
                zone={'zone_kind':'marked_no_passing_zone','striping_source':'native_map',
                      'stripe_y_m':0,'traffic_sweep_variant_id':variant,
                      'traffic_policy_sha256':traffic_sweep_audit.sha(attempt/'traffic-policy.json'),
                      'crossing_x_m':0,'approach_road_id':1,'approach_lane_id':-1,
                      'sample_interval_max_m':5,'approach_marking_samples':[
                          {'requested_x_m':x,'mapped_x_m':x,'road_id':1,
                           'lane_id':-1,'marking_type':'Solid'} for x in (-5,-1)]}
                zone.update(zone_source.validate(review,authority,zone))
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
                sources=('turn-history.jsonl','zone-context.json','traffic-policy.json',
                         'zone-review-source.json','zone-authority-source.txt')
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

    def test_rejects_resealed_false_authority_or_zone_review(self):
        with tempfile.TemporaryDirectory() as temp:
            records=self.inventory(temp)
            attempt=Path(records[0]['attempt'])
            authority=attempt/'zone-authority-source.txt'
            authority.write_text('changed synthetic authority\n')
            for name in ('acquisition.json','capture-seal.json'):
                packet=json.loads((attempt/name).read_text())
                if name=='acquisition.json':
                    packet['zone-authority-source.txt']['sha256']=traffic_sweep_audit.sha(authority)
                else:
                    packet['sources']['zone-authority-source.txt']=traffic_sweep_audit.sha(authority)
                write(attempt/name,packet)
            with self.assertRaisesRegex(ValueError,'authority designation source'):
                traffic_sweep_audit.audit(records)


if __name__=='__main__':unittest.main()
