import hashlib
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from bicycle_encounter import SourceError, construct_native, measure_attempt, verify_site
from encounter_control import command
from comparison_audit import ComparisonError, audit
from saved_attempt import finalize, probe_video
from delivery_decode import audit as audit_decode, finalize_delivery
from delivery_audit import audit as audit_delivery, compare_original_image_to_video

class Actor:
    def __init__(self,id):self.type_id=id;self.destroyed=False
    def destroy(self):self.destroyed=True
class BP:
    def __init__(self,id):self.id=id
class World:
    def __init__(self,fail_bike=False):self.spawned=[];self.fail_bike=fail_bike
    def get_map(self):return SimpleNamespace(name='TownTest')
    def get_blueprint_library(self):return SimpleNamespace(find=lambda x:BP(x))
    def try_spawn_actor(self,bp,transform):
        if self.fail_bike and len(self.spawned):return None
        a=Actor(bp.id);self.spawned.append(a);return a
class Carla:
    @staticmethod
    def Location(**kw):return kw
    @staticmethod
    def Rotation(**kw):return kw
    @staticmethod
    def Transform(*args):return args

class EncounterTests(unittest.TestCase):
    def setUp(self):
        scratch=HERE.parents[1]/'.runtime-work';scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        refs=[]
        device={'human_powered':True,'tandem_wheels':2,'one_wheel_diameter_in':26,'moped':False,'observed_blueprint_id':'vehicle.bh.crossbike','rendered_person_present':True}
        rider={'distinct_from_ego':True,'person_visible_in_review':True}
        rules={'jurisdiction':'Nevada','applicable_rules':['NRS 484B.270(1)'],'conduct_sources':[]}
        packets={'map.json':{'native_map_name':'TownTest','ego_route_xy':[[-10,0],[10,0]],'rider_route_xy':[[0,-10],[0,10]]},'bicycle.json':{'blueprint_id':'vehicle.bh.crossbike','classification':device},'rules.json':{'jurisdiction':'Nevada','applicable_rules':rules['applicable_rules']}}
        identity={'reviewer':'fixture-reviewer','assignment_id':'testing__C111260__NRS-484B-270-1__motor_vehicle_driver','cell_id':'C111260'}
        for name,observations in [('device-review.json',device),('rider-review.json',rider),('rules-review.json',rules)]:
            role=name.split('-')[0]
            packets[role+'-asset.json']={'original_fixture_role':role}
            packets[name]={**identity,'observations':observations}
        packets['conduct.json']={'observed_signal':'green','rider_path':'surveyed'}
        for name,packet in packets.items():
            p=self.root/name;p.write_text(json.dumps(packet));refs.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        for role in ('device','rider','rules'):
            name=role+'-review.json'
            packets[name]['original_asset']=next(ref for ref in refs if ref['path']==role+'-asset.json')
            path=self.root/name
            path.write_text(json.dumps(packets[name]))
            next(ref for ref in refs if ref['path']==name)['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        rules['conduct_sources']=[next(ref for ref in refs if ref['path']=='conduct.json')]
        packets['rules-review.json']['observations']=rules
        (self.root/'rules-review.json').write_text(json.dumps(packets['rules-review.json']))
        for ref in refs:
            if ref['path']=='rules-review.json':ref['sha256']=hashlib.sha256((self.root/ref['path']).read_bytes()).hexdigest()
        inventory={**identity,'rider_kind':'human_powered_bicycle','blueprint_id':'vehicle.bh.crossbike','lawful_riding_verdict':None,'intent_verdict':None,'interference_verdict':None,'device_observations':device,'rider_observations':rider,'rules_observations':rules,'original_sources':{role+'_review':next(ref for ref in refs if ref['path']==role+'-review.json') for role in ('device','rider','rules')}}
        p=self.root/'inventory.json';p.write_text(json.dumps(inventory));refs.append({'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        self.site={'assignment_id':'testing__C111260__NRS-484B-270-1__motor_vehicle_driver','cell_id':'C111260','layout':'intersection','maneuver':'travel','control':'cyclist','original_sources':refs,'map_source_path':'map.json','bicycle_classification_source_path':'bicycle.json','rider_rules_source_path':'rules.json','rider_inventory_source_path':'inventory.json','rider_kind':'human_powered_bicycle','native_map_name':'TownTest','jurisdiction':'Nevada','ego_blueprint_id':'vehicle.tesla.model3','bicycle_blueprint_id':'vehicle.bh.crossbike','bicycle_classification':device,'ego_route_xy':[[-10,0],[10,0]],'rider_route_xy':[[0,-10],[0,10]],'ego_actor_id':'ego','rider_actor_id':'rider','spawn_z_m':0.4,'ego_yaw_deg':0,'rider_yaw_deg':90,'control_proximity_m':8,'ego_travel_speed_mps':6}
    def test_routes_and_classification(self):
        self.assertEqual(verify_site(self.site,self.root),[(0.0,0.0)])
        self.site['bicycle_classification']['moped']=True
        with self.assertRaises(SourceError):verify_site(self.site,self.root)
    def test_reviewed_electric_rider_alternatives_and_source_tamper(self):
        def rewrite(name, value):
            path=self.root/name
            path.write_text(json.dumps(value),encoding='utf-8')
            for ref in self.site['original_sources']:
                if ref['path']==name:
                    ref['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            return {'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for kind, device in (
            ('electric_bicycle',{'electric_drive_observed':True,'pedals_observed':True,'motor_rating_w':350}),
            ('electric_scooter',{'electric_drive_observed':True,'standing_platform_observed':True,'wheel_count':2}),
        ):
            with self.subTest(kind=kind):
                source=copy.deepcopy(self.site)
                source['original_sources']=copy.deepcopy(self.site['original_sources'])
                self.site=source
                device.update(observed_blueprint_id='vehicle.bh.crossbike',rendered_person_present=True)
                source['rider_kind']=kind
                source['bicycle_classification']=device
                rewrite('bicycle.json',{'blueprint_id':source['bicycle_blueprint_id'],'classification':device})
                review=json.loads((self.root/'device-review.json').read_text())
                review['observations']=device
                device_ref=rewrite('device-review.json',review)
                inventory=json.loads((self.root/'inventory.json').read_text())
                inventory['rider_kind']=kind
                inventory['device_observations']=device
                inventory['original_sources']['device_review']=device_ref
                rewrite('inventory.json',inventory)
                self.assertEqual(verify_site(source,self.root),[(0.0,0.0)])
                self.assertEqual(construct_native(source,self.root,World(),Carla,'maintain_clearance')['rider_kind'],kind)
                review['observations']['rendered_person_present']=False
                rewrite('device-review.json',review)
                with self.assertRaisesRegex(ValueError,'hash mismatch'):
                    verify_site(source,self.root)
                rewrite('device-review.json',dict(review, observations=device))
        inventory=json.loads((self.root/'inventory.json').read_text())
        inventory['lawful_riding_verdict']=True
        rewrite('inventory.json',inventory)
        with self.assertRaisesRegex(ValueError,'unsupported legal verdict'):
            verify_site(self.site,self.root)
    def test_rider_review_requires_original_assets_and_exact_observations(self):
        self.assertEqual(verify_site(self.site,self.root),[(0.0,0.0)])
        asset=self.root/'device-asset.json'
        original_asset=asset.read_text(encoding='utf-8')
        asset.write_text('{"original_fixture_role":"altered"}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'original source hash mismatch'):
            verify_site(self.site,self.root)
        asset.write_text(original_asset,encoding='utf-8')
        review=self.root/'rider-review.json'
        packet=json.loads(review.read_text())
        packet['observations']['distinct_from_ego']=False
        review.write_text(json.dumps(packet),encoding='utf-8')
        for ref in self.site['original_sources']:
            if ref['path']==review.name:
                ref['sha256']=hashlib.sha256(review.read_bytes()).hexdigest()
        inventory_path=self.root/'inventory.json'
        inventory=json.loads(inventory_path.read_text(encoding='utf-8'))
        inventory['original_sources']['rider_review']['sha256']=hashlib.sha256(review.read_bytes()).hexdigest()
        inventory_path.write_text(json.dumps(inventory),encoding='utf-8')
        for ref in self.site['original_sources']:
            if ref['path']==inventory_path.name:
                ref['sha256']=hashlib.sha256(inventory_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'rider observations do not match reviewed source'):
            verify_site(self.site,self.root)
    def test_source_hash_and_geometry_rejection(self):
        original=(self.root/'map.json').read_text()
        (self.root/'map.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(SourceError,'hash mismatch'):verify_site(self.site,self.root)
        (self.root/'map.json').write_text(original);self.site['original_sources'][0]['sha256']=hashlib.sha256((self.root/'map.json').read_bytes()).hexdigest()
        self.site['rider_route_xy']=[[12,-10],[12,10]]
        with self.assertRaisesRegex(SourceError,'packet mismatch'):verify_site(self.site,self.root)
        packet=json.loads(original);packet['rider_route_xy']=self.site['rider_route_xy'];(self.root/'map.json').write_text(json.dumps(packet));self.site['original_sources'][0]['sha256']=hashlib.sha256((self.root/'map.json').read_bytes()).hexdigest()
        with self.assertRaisesRegex(SourceError,'never intersect'):verify_site(self.site,self.root)
    def test_native_spawn_and_cleanup(self):
        world=World();out=construct_native(self.site,self.root,world,Carla,'maintain_clearance')
        self.assertEqual(len(out['actors']),2)
        self.assertEqual(out['crossings_xy'],[(0.0,0.0)])
        world=World(True)
        with self.assertRaisesRegex(SourceError,'bicycle spawn failed'):construct_native(self.site,self.root,world,Carla,'cross_rider_path')
        self.assertTrue(world.spawned[0].destroyed)
    def test_controller_changes_command(self):
        clear=command(self.site,self.root,'maintain_clearance',[-4,0],[0,-4],3,2)
        block=command(self.site,self.root,'cross_rider_path',[-4,0],[0,-4],3,2)
        self.assertEqual(clear['target_speed_mps'],0)
        self.assertEqual(block['target_speed_mps'],6)
        self.assertIsNone(block['legal_verdict'])
    def test_original_measurement(self):
        rows=[]
        for i in range(3):
            rows.append({'frame':i,'ego_id':'ego','rider_id':'rider','ego_blueprint_id':self.site['ego_blueprint_id'],'rider_blueprint_id':self.site['bicycle_blueprint_id'],'mode_command':'cross_rider_path','command_source':'controller_log','rider_visual_present':True,'ego_xy':[-3+i,0],'rider_xy':[0,-3+i]})
        p=self.root/'events.json';p.write_text(json.dumps(rows));ref={'path':'events.json','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        out=measure_attempt(self.site,self.root,ref,'cross_rider_path')
        self.assertEqual(out['frame_count'],3);self.assertIsNone(out['intent_verdict'])
        rows[1]['frame']=3;p.write_text(json.dumps(rows));ref['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(SourceError,'noncontinuous'):measure_attempt(self.site,self.root,ref,'cross_rider_path')
    def test_independent_comparison(self):
        fixed={k:'sealed' for k in ('map_sha256','bicycle_classification_sha256','rider_rules_sha256','rider_inventory_sha256','ego_route_sha256','rider_route_sha256','camera_profile_sha256','ego_blueprint_id','bicycle_blueprint_id')}
        fixed['rider_kind']='human_powered_bicycle'
        fixed.update(duration_frames=3,frame_count=3,original_sources=[{'path':'sealed'}],visual_rider_witness={'camera':'front'},lawful_riding_verdict=None,intent_verdict=None,interference_verdict=None)
        l=dict(fixed,mode='maintain_clearance',waiting_command_frames=2)
        r=dict(fixed,mode='cross_rider_path',travel_command_frames=3)
        self.assertEqual(audit(l,r)['comparison_id'],'bicycle_encounter_behavior')
        r['camera_profile_sha256']='different'
        with self.assertRaisesRegex(ComparisonError,'fixed condition'):audit(l,r)
        r['camera_profile_sha256']='sealed';r['intent_verdict']=True
        with self.assertRaisesRegex(ComparisonError,'unsupported legal verdict'):audit(l,r)

    def test_saved_full_history_and_four_camera_sources(self):
        frames=900
        rows=[]
        for i in range(frames):
            rows.append({'frame':i,'camera_frame':i,'ego_id':'ego','rider_id':'rider',
                         'ego_blueprint_id':self.site['ego_blueprint_id'],
                         'rider_blueprint_id':self.site['bicycle_blueprint_id'],
                         'mode_command':'maintain_clearance','command_source':'controller_log',
                         'target_speed_mps':0 if 100<=i<200 else 6,
                         'rider_visual_present':i>=50,
                         'ego_xy':[-10+i/60,0],'rider_xy':[0,-10+i/60]})
        event_path=self.root/'events.json';event_path.write_text(json.dumps(rows),encoding='utf-8')
        event_ref={'path':'events.json','sha256':hashlib.sha256(event_path.read_bytes()).hexdigest()}
        cameras={}
        for view in ('overview','approach','reference_corner','driver_reference'):
            path=self.root/(view+'.mp4');path.write_bytes(('test-'+view).encode())
            cameras[view]={'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        def probe(path):
            return {'fps':20,'frame_count':frames,'width':1920,'height':1080}
        summary=finalize(self.site,self.root,event_ref,cameras,'maintain_clearance',probe)
        self.assertEqual(summary['frame_count'],frames)
        self.assertEqual(summary['waiting_command_frames'],100)
        self.assertGreater(summary['observed_rider_motion_m'],0)
        self.assertFalse(summary['pixel_visibility_verified'])
        self.assertIsNone(summary['interference_verdict'])
        broken=dict(cameras);broken.pop('driver_reference')
        with self.assertRaisesRegex(SourceError,'four exact camera'):
            finalize(self.site,self.root,event_ref,broken,'maintain_clearance',probe)
        with self.assertRaisesRegex(SourceError,'camera frame rate'):
            finalize(self.site,self.root,event_ref,cameras,'maintain_clearance',
                     lambda path:dict(probe(path),frame_count=899))
        wrong=dict(cameras);wrong['approach']=dict(cameras['approach'],sha256='0'*64)
        with self.assertRaisesRegex(SourceError,'hash mismatch'):
            finalize(self.site,self.root,event_ref,wrong,'maintain_clearance',probe)
        rows[10]['camera_frame']=11
        event_path.write_text(json.dumps(rows),encoding='utf-8')
        event_ref['sha256']=hashlib.sha256(event_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(SourceError,'frame join'):
            finalize(self.site,self.root,event_ref,cameras,'maintain_clearance',probe)

    def test_probe_counts_decoded_video_frames(self):
        path=self.root/'tiny.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=32x32:r=20',
                        '-frames:v','3','-c:v','mpeg4',str(path)],check=True)
        self.assertEqual(probe_video(path),
                         {'fps':20.0,'frame_count':3,'width':32,'height':32})

    def test_probe_rejects_second_original_video_stream(self):
        path=self.root/'two-streams.mkv'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=32x32:r=20',
                        '-f','lavfi','-i','color=c=red:s=32x32:r=20',
                        '-map','0:v:0','-map','1:v:0','-frames:v','3',
                        '-c:v','ffv1',str(path)],check=True)
        with self.assertRaisesRegex(SourceError,'exactly one original video stream'):
            probe_video(path)

    def test_full_decode_of_four_sealed_original_streams(self):
        cameras={}
        for view in ('overview','approach','reference_corner','driver_reference'):
            path=self.root/(view+'.mp4')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                            'color=c=blue:s=32x32:r=20','-frames:v','3',
                            '-c:v','mpeg4',str(path)],check=True)
            cameras[view]={'path':path.name,
                           'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        receipt=audit_decode(self.root,cameras,3)
        self.assertTrue(receipt['full_video_decode'])
        self.assertFalse(receipt['pixel_visibility_verified'])
        self.assertEqual(set(receipt['camera_decode_receipts']),set(cameras))
        self.assertTrue(all(len(v['framemd5_sha256'])==64
                            for v in receipt['camera_decode_receipts'].values()))
        rows=[]
        for i in range(3):
            rows.append({'frame':i,'camera_frame':i,'ego_id':'ego','rider_id':'rider',
                         'ego_blueprint_id':self.site['ego_blueprint_id'],
                         'rider_blueprint_id':self.site['bicycle_blueprint_id'],
                         'mode_command':'cross_rider_path','command_source':'controller_log',
                         'target_speed_mps':6,'rider_visual_present':False,
                         'ego_xy':[-3+i,0],'rider_xy':[0,-3+i]})
        event_path=self.root/'events.json'
        event_path.write_text(json.dumps(rows),encoding='utf-8')
        event_ref={'path':event_path.name,
                   'sha256':hashlib.sha256(event_path.read_bytes()).hexdigest()}
        joined=finalize_delivery(self.site,self.root,event_ref,cameras,
                                 'cross_rider_path',3)
        self.assertEqual(joined['frame_count'],3)
        self.assertTrue(joined['full_video_decode'])
        self.assertIsNone(joined['interference_verdict'])
        with self.assertRaisesRegex(SourceError,'frame rate or duration'):
            audit_decode(self.root,cameras,4)
        (self.root/'approach.mp4').write_bytes(b'changed')
        with self.assertRaisesRegex(SourceError,'hash mismatch'):
            audit_decode(self.root,cameras,3)
        cameras['approach']['sha256']=hashlib.sha256(
            (self.root/'approach.mp4').read_bytes()).hexdigest()
        with self.assertRaises((subprocess.CalledProcessError,SourceError)):
            audit_decode(self.root,cameras,3)

    def test_independent_delivery_review_binds_originals_and_rejects_stale_pixels(self):
        case=self.site['assignment_id']+'__cross_rider_path'
        self.site['case_id']=case
        site_path=self.root/'site.json'
        site_path.write_text(json.dumps(self.site),encoding='utf-8')
        rows=[{'frame':i,'camera_frame':i,'ego_id':'ego','rider_id':'rider',
               'ego_blueprint_id':self.site['ego_blueprint_id'],
               'rider_blueprint_id':self.site['bicycle_blueprint_id'],
               'mode_command':'cross_rider_path','command_source':'controller_log',
               'target_speed_mps':6,'rider_visual_present':True,
               'ego_xy':[-3+i,0],'rider_xy':[0,-3+i]} for i in range(3)]
        event_path=self.root/'events.json'
        event_path.write_text(json.dumps(rows),encoding='utf-8')
        def ref(path):
            return {'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        frame_map_path=self.root/'frame-map.jsonl'
        frame_map_path.write_text(''.join(json.dumps({'video_frame':i,'carla_frame':i,
                                                       'native_frame':i,'time_s':i/20})+'\n'
                                          for i in range(3)),encoding='utf-8')
        refs={'site':ref(site_path),'events':ref(event_path),
              'frame_map':ref(frame_map_path)}
        originals={}
        for view in ('overview','approach','reference_corner','driver_reference'):
            path=self.root/(view+'.mp4')
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
                            'color=c=blue:s=32x32:r=20','-frames:v','3',
                            '-c:v','mpeg4',str(path)],check=True)
            refs[view]=ref(path)
            originals[view]=[]
            for i in range(3):
                image=self.root/(view+'-'+str(i)+'.png')
                from PIL import Image
                Image.new('RGB',(32,32),'blue').save(image)
                originals[view].append({'frame':i,'time_s':i/20,'image':ref(image)})
        index={'format':'c111260-original-index-v1','case_id':case,
               'frame_count':3,'sources':refs,'camera_originals':originals}
        index_path=self.root/'source-index.json'
        index_path.write_text(json.dumps(index),encoding='utf-8')
        measured=finalize_delivery(self.site,self.root,refs['events'],
                                   {view:refs[view] for view in ('overview','approach','reference_corner','driver_reference')},
                                   'cross_rider_path',3)
        review={'case_id':case,'source_index_sha256':ref(index_path)['sha256'],
                'site_sha256':refs['site']['sha256'],
                'events_sha256':refs['events']['sha256'],
                'views':{view:{'video_sha256':refs[view]['sha256'],
                               'framemd5_sha256':measured['camera_decode_receipts'][view]['framemd5_sha256'],
                               'samples':[{'frame':1,'rider_visible':True,
                                           'rider_kind':'human_powered_bicycle',
                                           'original_png_sha256':originals[view][1]['image']['sha256'],
                                           'reviewer':'fixture-reviewer'}]}
                         for view in ('overview','approach','reference_corner','driver_reference')},
                'physical_review':{'completed':True,'first_frame':0,'last_frame':2,
                                   'reviewer':'fixture-reviewer'},
                'lawful_riding_verdict':None,'intent_verdict':None,
                'interference_verdict':None}
        review_path=self.root/'pixel-review.json'
        review_path.write_text(json.dumps(review),encoding='utf-8')
        result=audit_delivery(self.root,case,review_path,expected_frames=3)
        self.assertTrue(result['checks']['actual_pixels'])
        self.assertTrue(result['checks']['physical_completion'])
        from PIL import Image
        wrong_image=self.root/'wrong.png'
        Image.new('RGB',(32,32),'red').save(wrong_image)
        with self.assertRaisesRegex(ValueError,'original PNG and encoded video frame differ'):
            compare_original_image_to_video(self.root/'overview.mp4',1,wrong_image,32,32)
        bad=copy.deepcopy(review)
        bad['views']['approach']['framemd5_sha256']='0'*64
        review_path.write_text(json.dumps(bad),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'pixel review video/decode binding differs'):
            audit_delivery(self.root,case,review_path,expected_frames=3)
        bad=copy.deepcopy(review)
        bad['physical_review']['completed']=False
        review_path.write_text(json.dumps(bad),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'physical encounter review'):
            audit_delivery(self.root,case,review_path,expected_frames=3)
        bad=copy.deepcopy(review)
        bad['views']['overview']['samples'][0]['original_png_sha256']='0'*64
        review_path.write_text(json.dumps(bad),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'unresolved rider pixel review'):
            audit_delivery(self.root,case,review_path,expected_frames=3)
        review_path.write_text(json.dumps(review),encoding='utf-8')
        index['case_id']=self.site['assignment_id']+'__maintain_clearance'
        index_path.write_text(json.dumps(index),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'original source index identity'):
            audit_delivery(self.root,case,review_path,expected_frames=3)

if __name__=='__main__':unittest.main()
