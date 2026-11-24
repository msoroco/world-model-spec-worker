import hashlib
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
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        refs=[]
        packets={'map.json':{'native_map_name':'TownTest','ego_route_xy':[[-10,0],[10,0]],'rider_route_xy':[[0,-10],[0,10]]},'bicycle.json':{'blueprint_id':'vehicle.bh.crossbike','classification':{'human_powered':True,'tandem_wheels':2,'one_wheel_diameter_in':26,'moped':False}},'rules.json':{'jurisdiction':'Nevada','applicable_rules':['NRS 484B.270(1)']}}
        for name,packet in packets.items():
            p=self.root/name;p.write_text(json.dumps(packet));refs.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        self.site={'assignment_id':'testing__C111260__NRS-484B-270-1__motor_vehicle_driver','cell_id':'C111260','layout':'intersection','maneuver':'travel','control':'cyclist','original_sources':refs,'map_source_path':'map.json','bicycle_classification_source_path':'bicycle.json','rider_rules_source_path':'rules.json','native_map_name':'TownTest','jurisdiction':'Nevada','ego_blueprint_id':'vehicle.tesla.model3','bicycle_blueprint_id':'vehicle.bh.crossbike','bicycle_classification':{'human_powered':True,'tandem_wheels':2,'one_wheel_diameter_in':26,'moped':False},'ego_route_xy':[[-10,0],[10,0]],'rider_route_xy':[[0,-10],[0,10]],'ego_actor_id':'ego','rider_actor_id':'rider','spawn_z_m':0.4,'ego_yaw_deg':0,'rider_yaw_deg':90,'control_proximity_m':8,'ego_travel_speed_mps':6}
    def test_routes_and_classification(self):
        self.assertEqual(verify_site(self.site,self.root),[(0.0,0.0)])
        self.site['bicycle_classification']['moped']=True
        with self.assertRaises(SourceError):verify_site(self.site,self.root)
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
        fixed={k:'sealed' for k in ('map_sha256','bicycle_classification_sha256','rider_rules_sha256','ego_route_sha256','rider_route_sha256','camera_profile_sha256','ego_blueprint_id','bicycle_blueprint_id')}
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

if __name__=='__main__':unittest.main()
