import importlib.util
import hashlib
import sys
from pathlib import Path
import unittest

FOLDER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FOLDER))
from traffic_sweep import select as select_traffic
spec=importlib.util.spec_from_file_location('runner',FOLDER/'runner.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class Marking:
    type='Solid'
class Waypoint:
    left_lane_marking=Marking()
class Map:
    def __init__(self,marking=True):self.marking=marking
    def get_waypoint(self,location):return Waypoint() if self.marking else None
class Library:
    def filter(self,pattern):return [pattern]
class World:
    def __init__(self):self.calls=[]
    def get_blueprint_library(self):return Library()
    def spawn_actor(self,blueprint,transform):
        actor=object();self.calls.append((blueprint,transform,actor));return actor

class ConstructionTests(unittest.TestCase):
    def setUp(self):self.scene=runner.load_scene()
    def test_stripe_geometry_and_signal_station(self):
        self.assertTrue(runner.crosses_stripe(self.scene))
        self.assertLess(self.scene['signal_start_x_m'],self.scene['crossing_x_m'])
        self.assertGreaterEqual(self.scene['crossing_x_m']-4-self.scene['signal_start_x_m'],300*.3048)
        self.assertEqual(runner.controller_command(self.scene,0,True)['left_signal'],
                         self.scene['signal_enabled'])
    def test_actual_spawn_calls_and_opposing_direction(self):
        world=World();actors=runner.spawn_scene(world,self.scene,lambda *args:args)
        self.assertEqual(set(actors),{'ego','oncoming','following'})
        self.assertEqual([c[1][-1] for c in world.calls],[0,180,0])
        self.assertEqual(world.calls[1][1][1],self.scene['opposing_lane_center_y_m'])
    def test_map_marking_rejection(self):
        self.assertIsNotNone(runner.require_marking(Map(),(0,0)))
        with self.assertRaisesRegex(ValueError,'no approach waypoint'):
            runner.require_marking(Map(False),(0,0))
    def test_unsignaled_variant_keeps_route(self):
        other=dict(self.scene,signal_enabled=False)
        self.assertEqual(runner.route(self.scene),runner.route(other))
        self.assertFalse(runner.controller_command(other,0,True)['left_signal'])

if __name__=='__main__':unittest.main()

import hashlib
import json
import tempfile
spec_analysis=importlib.util.spec_from_file_location('analysis',FOLDER/'analysis.py')
analysis=importlib.util.module_from_spec(spec_analysis);spec_analysis.loader.exec_module(analysis)

class SavedAnalysisTests(unittest.TestCase):
    def fixture(self,root,signaled):
        root=Path(root);rows=[]
        for frame,y in enumerate((-1.75,-0.4,0.25,1.75)):
            vertices=[[frame,y-.1,0],[frame+1,y-.1,0],
                      [frame+1,y+.1,0],[frame,y+.1,0]]
            rows.append({'frame':frame,'time_s':frame/20,'ego_center_y_m':y,
                         'ego_body_vertices_m':vertices,
                         'left_signal':bool(signaled and frame>=1),
                         'oncoming_velocity_xy_mps':[-2.0+0.1*frame,0.0],
                         'following_velocity_xy_mps':[2.0-0.1*frame,0.0],
                         'oncoming_body_gap_m':20-frame,'following_body_gap_m':15+frame})
        (root/'turn-history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (root/'zone-context.json').write_text(json.dumps({'zone_kind':'marked_no_passing_zone',
                                                          'striping_source':'native_map','stripe_y_m':0.0}))
        acquisition={name:{'kind':'original_native','sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()}
                     for name in ('turn-history.jsonl','zone-context.json')}
        (root/'acquisition.json').write_text(json.dumps(acquisition))
        return root
    def test_signaled_crossing(self):
        with tempfile.TemporaryDirectory() as temp:
            m=analysis.measure(self.fixture(temp,True))
            self.assertEqual(m['crossing_frame'],2)
            self.assertTrue(m['signal_active_at_crossing'])
            self.assertLess(m['signal_started_s'],m['crossing_time_s'])
            self.assertGreater(m['traffic_speed_observations']['oncoming']['observed_range_mps'],0)
            response=m['traffic_response_window']
            self.assertFalse(response['full_window_observed'])
            self.assertEqual(response['pre_sample_count'],2)
            self.assertEqual(response['crossing_and_post_sample_count'],2)
            self.assertIsNotNone(response['participants']['oncoming']['mean_speed_change_mps'])
    def test_unsignaled_crossing(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(analysis.measure(self.fixture(temp,False))['signal_started_s'])

    def test_response_window_completeness_and_invalid_gap(self):
        rows=[{'frame':index,'time_s':index/20,
               'oncoming_body_gap_m':20-index/20,
               'following_body_gap_m':15+index/20} for index in range(100)]
        speeds={role:{'samples_mps':[2-index/100 for index in range(100)]}
                for role in ('oncoming','following')}
        complete=analysis.traffic_response(rows,2.5,speeds)
        self.assertTrue(complete['full_window_observed'])
        self.assertLess(complete['participants']['oncoming']['mean_speed_change_mps'],0)
        del rows[50:53]
        incomplete=analysis.traffic_response(rows,2.5,
                    {role:{'samples_mps':[2-index/100 for index in range(97)]}
                     for role in ('oncoming','following')})
        self.assertFalse(incomplete['full_window_observed'])
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True)
            history=path/'turn-history.jsonl'
            values=[json.loads(line) for line in history.read_text().splitlines()]
            values[0]['oncoming_body_gap_m']=float('nan')
            history.write_text(''.join(json.dumps(row)+'\n' for row in values))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition['turn-history.jsonl']['sha256']=hashlib.sha256(history.read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError,'invalid traffic gap'):
                analysis.measure(path)
    def test_stale_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True)
            (path/'zone-context.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'stale original Native source'):
                analysis.measure(path)
    def test_measurement_report_binds_original_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True)
            item=analysis.build_report(path)['measurements']['left_turn_crossing_measurement']
            self.assertEqual(item['method'],'measure')
            self.assertEqual(item['sources']['turn-history.jsonl'],hashlib.sha256((path/'turn-history.jsonl').read_bytes()).hexdigest())
            self.assertEqual(item['value']['crossing_frame'],2)
    def test_missing_required_history_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True);(path/'turn-history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source: turn-history.jsonl'):
                analysis.build_report(path)
    def test_body_edge_precedes_center_crossing(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True)
            rows=[json.loads(line) for line in (path/'turn-history.jsonl').read_text().splitlines()]
            for vertex in rows[1]['ego_body_vertices_m']:
                if vertex[1]>rows[1]['ego_center_y_m']:
                    vertex[1]=.05
            (path/'turn-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition['turn-history.jsonl']['sha256']=hashlib.sha256((path/'turn-history.jsonl').read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            measured=analysis.measure(path)
            self.assertEqual(measured['crossing_frame'],1)
            self.assertLess(rows[1]['ego_center_y_m'],0)

    def test_observed_continuous_signal_distance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.fixture(temp,True)
            rows=[json.loads(line) for line in (path/'turn-history.jsonl').read_text().splitlines()]
            for row,x in zip(rows,(-200.,-100.,-4.,0.)):
                row['ego_center_x_m']=x
            def measured():
                (path/'turn-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                acquisition=json.loads((path/'acquisition.json').read_text())
                acquisition['turn-history.jsonl']['sha256']=hashlib.sha256((path/'turn-history.jsonl').read_bytes()).hexdigest()
                (path/'acquisition.json').write_text(json.dumps(acquisition))
                return analysis.measure(path)
            self.assertTrue(measured()['signal_300ft_observed'])
            rows[1]['left_signal']=False
            self.assertFalse(measured()['signal_300ft_observed'])

spec_compare=importlib.util.spec_from_file_location('comparison_audit',FOLDER/'comparison_audit.py')
compare=importlib.util.module_from_spec(spec_compare);spec_compare.loader.exec_module(compare)

class ComparisonAuditTests(unittest.TestCase):
    def records(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            measured_a=analysis.measure(SavedAnalysisTests().fixture(a,True))
            measured_b=analysis.measure(SavedAnalysisTests().fixture(b,False))
        fixed={name:'same' for name in compare.FIXED};fixed['duration_s']=30
        return dict(fixed,measurement=measured_a),dict(fixed,measurement=measured_b)
    def test_source_bound_comparison(self):
        a,b=self.records();self.assertTrue(compare.audit(a,b)['passed'])
    def test_missing_measurement_rejected(self):
        a,b=self.records();del a['measurement']
        with self.assertRaisesRegex(ValueError,'missing source-bound'):
            compare.audit(a,b)
    def test_changed_map_rejected(self):
        a,b=self.records();b['map_sha256']='different'
        with self.assertRaisesRegex(ValueError,'fixed condition differs'):
            compare.audit(a,b)

spec_delivery=importlib.util.spec_from_file_location('delivery_audit',FOLDER/'delivery_audit.py')
delivery=importlib.util.module_from_spec(spec_delivery);spec_delivery.loader.exec_module(delivery)

class DeliveryAuditTests(unittest.TestCase):
    def fixture(self,root):
        root=Path(root)
        trace=root/'trace.jsonl';trace.write_text(json.dumps({'frame':10,'time_s':0.5})+'\n')
        mapping=root/'video_frames.jsonl';mapping.write_text(json.dumps({'video_frame':0,'carla_frame':10,'time_s':0.5})+'\n')
        (root/'raw.mkv').write_bytes(b'test-video-placeholder')
        (root/'result.json').write_text(json.dumps({'case_id':'case-1','setup_confirmed':True,
            'behavior_attempted':True,'maneuver_completed':True}))
        body=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]
        history={'frame':10,'time_s':0.5,'ego_body_vertices_m':body,
            'oncoming_body_vertices_m':[[v[0]+5,v[1],v[2]] for v in body],
            'following_body_vertices_m':[[v[0]-6,v[1],v[2]] for v in body],
            'left_signal':True,'oncoming_body_gap_m':4.0,'following_body_gap_m':5.0}
        history['oncoming_velocity_xy_mps']=[-2.0,0.0]
        history['following_velocity_xy_mps']=[2.0,0.0]
        history['traffic_command_velocity_x_mps']={'oncoming':-2.0,'following':2.0}
        (root/'turn-history.jsonl').write_text(json.dumps(history)+'\n')
        scene=json.loads((FOLDER/'scene.json').read_text())
        (root/'scene.json').write_text(json.dumps(scene))
        _,policy,_=select_traffic(scene,'baseline')
        (root/'traffic-policy.json').write_text(json.dumps(policy))
        (root/'acquisition-provenance.json').write_text(json.dumps({
            'traffic_sweep_variant_id':'baseline',
            'traffic_policy_sha256':delivery.sha(root/'traffic-policy.json')}))
        authority=b'synthetic zone authority fixture\n'
        (root/'zone-authority-source.txt').write_bytes(authority)
        packet={'format':'worker-zone-review-source-v1','reviewer':'CPU fixture',
                'review_method':'source/map join fixture','authority_citation':'fixture',
                'authority_source_path':str(root/'zone-authority-source.txt'),
                'authority_source_sha256':hashlib.sha256(authority).hexdigest(),
                'designation':'official_no_passing_zone','destination_kind':'other_left_turn',
                'subsections_3_and_4_reviewed':True,'road_id':1,'lane_id':-1,
                'zone_x_limits_m':[-10,10]}
        (root/'zone-review-source.json').write_text(json.dumps(packet))
        zone={'zone_kind':'marked_no_passing_zone','striping_source':'native_map',
              'approach_road_id':1,'approach_lane_id':-1,'crossing_x_m':0,
              'sample_interval_max_m':5,'approach_marking_samples':[
                  {'requested_x_m':x,'mapped_x_m':x,'road_id':1,'lane_id':-1,'marking_type':'Solid'}
                  for x in (-5,-1)]}
        from zone_source import validate as validate_zone_source
        zone.update(validate_zone_source(packet,authority,zone))
        zone['traffic_sweep_variant_id']='baseline'
        zone['traffic_policy_sha256']=delivery.sha(root/'traffic-policy.json')
        (root/'zone-context.json').write_text(json.dumps(zone))
        (root/'acquisition.json').write_text(json.dumps({name:{'kind':'original_native',
            'sha256':delivery.sha(root/name)} for name in ('turn-history.jsonl','zone-context.json',
                'zone-review-source.json','zone-authority-source.txt','traffic-policy.json')}))
        seal={'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{name:delivery.sha(root/name) for name in ('trace.jsonl','video_frames.jsonl','raw.mkv','result.json','turn-history.jsonl','zone-context.json','zone-review-source.json','zone-authority-source.txt','traffic-policy.json','acquisition-provenance.json','acquisition.json')}}
        (root/'capture-seal.json').write_text(json.dumps(seal))
        (root/'native-exit.json').write_text(json.dumps({'event':'native_exit','capture_seal_sha256':delivery.sha(root/'capture-seal.json')}))
        (root/'owner-release.json').write_text(json.dumps({'event':'owner_released','operator_attested':True,
            'native_exit_sha256':delivery.sha(root/'native-exit.json')}))
        (root/'processing.json').write_text(json.dumps({'format':'worker-saved-processing','passed':True,
            'recorded_only':True,'analysis_directory':str(root),'result':str(root/'result.json'),
            'result_sha256':delivery.sha(root/'result.json')}))
        (root/'source-decode.json').write_text('{}')
        return root
    def verifier(self,*args,**kwargs):return {'passed':True}
    def test_positive_source_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp)
            self.assertTrue(delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)['passed'])
    def test_resealed_wrong_traffic_command_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp)
            history=p/'turn-history.jsonl'
            row=json.loads(history.read_text())
            row['traffic_command_velocity_x_mps']['oncoming']=-3.0
            history.write_text(json.dumps(row)+'\n')
            acquisition=json.loads((p/'acquisition.json').read_text())
            acquisition['turn-history.jsonl']['sha256']=delivery.sha(history)
            (p/'acquisition.json').write_text(json.dumps(acquisition))
            seal=json.loads((p/'capture-seal.json').read_text())
            for name in ('turn-history.jsonl','acquisition.json'):
                seal['sources'][name]=delivery.sha(p/name)
            (p/'capture-seal.json').write_text(json.dumps(seal))
            (p/'native-exit.json').write_text(json.dumps({'event':'native_exit',
                'capture_seal_sha256':delivery.sha(p/'capture-seal.json')}))
            (p/'owner-release.json').write_text(json.dumps({'event':'owner_released',
                'operator_attested':True,'native_exit_sha256':delivery.sha(p/'native-exit.json')}))
            with self.assertRaisesRegex(ValueError,'recorded traffic commands differ'):
                delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)
    def test_missing_sealed_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp);(p/'trace.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'sealed original missing'):
                delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)
    def test_failed_physical_completion_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp);result=json.loads((p/'result.json').read_text());result['maneuver_completed']=False
            (p/'result.json').write_text(json.dumps(result));seal=json.loads((p/'capture-seal.json').read_text());seal['sources']['result.json']=delivery.sha(p/'result.json');(p/'capture-seal.json').write_text(json.dumps(seal));(p/'native-exit.json').write_text(json.dumps({'event':'native_exit','capture_seal_sha256':delivery.sha(p/'capture-seal.json')}));(p/'owner-release.json').write_text(json.dumps({'event':'owner_released','operator_attested':True,'native_exit_sha256':delivery.sha(p/'native-exit.json')}))
            with self.assertRaisesRegex(ValueError,'physical completion'):
                delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)
    def test_missing_participant_history_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp)
            row=json.loads((p/'turn-history.jsonl').read_text());del row['following_body_vertices_m']
            (p/'turn-history.jsonl').write_text(json.dumps(row)+'\n')
            acquisition=json.loads((p/'acquisition.json').read_text())
            acquisition['turn-history.jsonl']['sha256']=delivery.sha(p/'turn-history.jsonl')
            (p/'acquisition.json').write_text(json.dumps(acquisition))
            seal=json.loads((p/'capture-seal.json').read_text())
            for name in ('turn-history.jsonl','acquisition.json'):
                seal['sources'][name]=delivery.sha(p/name)
            (p/'capture-seal.json').write_text(json.dumps(seal))
            (p/'native-exit.json').write_text(json.dumps({'event':'native_exit','capture_seal_sha256':delivery.sha(p/'capture-seal.json')}))
            (p/'owner-release.json').write_text(json.dumps({'event':'owner_released','operator_attested':True,
                'native_exit_sha256':delivery.sha(p/'native-exit.json')}))
            with self.assertRaisesRegex(ValueError,'participant/body history incomplete'):
                delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)
    def test_unverified_zone_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=self.fixture(temp)
            zone=json.loads((p/'zone-context.json').read_text());zone['zone_extent_verified']=False
            (p/'zone-context.json').write_text(json.dumps(zone))
            acquisition=json.loads((p/'acquisition.json').read_text())
            acquisition['zone-context.json']['sha256']=delivery.sha(p/'zone-context.json')
            (p/'acquisition.json').write_text(json.dumps(acquisition))
            seal=json.loads((p/'capture-seal.json').read_text())
            for name in ('zone-context.json','acquisition.json'):
                seal['sources'][name]=delivery.sha(p/name)
            (p/'capture-seal.json').write_text(json.dumps(seal))
            (p/'native-exit.json').write_text(json.dumps({'event':'native_exit','capture_seal_sha256':delivery.sha(p/'capture-seal.json')}))
            (p/'owner-release.json').write_text(json.dumps({'event':'owner_released','operator_attested':True,
                'native_exit_sha256':delivery.sha(p/'native-exit.json')}))
            with self.assertRaisesRegex(ValueError,'reviewed zone source differs'):
                delivery.audit(p,p/'processing.json',p/'source-decode.json',self.verifier)
