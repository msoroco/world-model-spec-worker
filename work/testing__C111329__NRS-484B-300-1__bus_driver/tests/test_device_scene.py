import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
def mod(name):
    spec=importlib.util.spec_from_file_location(name,BASE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
scene=mod('device_scene'); control=mod('device_control'); audit=mod('comparison_audit')

class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        def ref(name,data):
            p=self.root/name;p.write_text(json.dumps(data));return {'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        self.ref=ref
        refs=[ref(k,{'surveyed':k}) for k in ('map','device','route','authority')]
        self.site={'cell_id':'C111329','actor':'bus_driver','native_map_name':'TownSurvey','device_id':17,
                   'ego_approach_id':'north','governs_ego_approach':True,'original_sources':refs,
                   'map_source_path':'map','device_source_path':'device','route_source_path':'route',
                   'authority_source_path':'authority','bus_route_xy':[[0,0],[10,0],[20,0]],
                   'stop_line_xy':[8,0],'bus_clearance_width_m':3.5,'bus_body_width_m':2.6,
                   'bus_clearance_height_m':4.3,'bus_body_height_m':3.4,'bus_blueprint_id':'vehicle.bus',
                   'spawn_z_m':0.5,'approach_yaw_deg':0,'hold_brake':0.7,'proceed_throttle':0.25}
    def event(self,frame,x,police=None):
        return {'frame':frame,'device_id':17,'facing_approach_id':'north','bus_actor_id':42,
                'bus_blueprint_id':'vehicle.bus','aspect':'red','bus_front_xy':[x,0],
                'police_direction':police,'police_direction_source':'authority' if police else None,
                'placement_source':'authority','nrs_307_context_source':'authority'}
    def test_original_entry_and_hold(self):
        rows=[self.event(1,0),self.event(2,7),self.event(3,9)]
        out=scene.measure_attempt(self.site,self.root,self.ref('events',rows))
        self.assertEqual(out['first_line_entry']['frame'],3)
        self.assertLess(out['first_line_entry']['bus_front_signed_distance_m'],0)
        self.assertIsNone(out['legal_compliance_verdict'])
        hold=scene.measure_attempt(self.site,self.root,self.ref('hold',[self.event(1,0),self.event(2,6),self.event(3,7)]))
        self.assertIsNone(hold['first_line_entry'])
    def test_missing_source_and_wrong_head_fail(self):
        rows=[self.event(1,0),self.event(2,7),self.event(3,9)]
        r=self.ref('events',rows);(self.root/'events').write_text('[]')
        with self.assertRaisesRegex(scene.SourceError,'hash mismatch'):scene.measure_attempt(self.site,self.root,r)
        rows[1]['device_id']=99
        with self.assertRaisesRegex(scene.SourceError,'identity'):scene.measure_attempt(self.site,self.root,self.ref('changed',rows))
    def test_insufficient_bus_clearance_fails(self):
        self.site['bus_clearance_width_m']=2.4
        with self.assertRaisesRegex(scene.SourceError,'clearance'):scene.validate_site(self.site,self.root)
    def test_control_requires_bound_red_and_police_source(self):
        obs={'device_id':17,'facing_approach_id':'north','aspect':'red','frame':4,'bus_front_signed_distance_m':1}
        self.assertEqual(control.command(self.site,obs,'hold_red')['target'],'remain_before_line')
        self.assertEqual(control.command(self.site,obs,'enter_red')['target'],'continue_surveyed_route')
        self.assertEqual(control.command(self.site,dict(obs,aspect='green'),'proceed_when_green')['target'],'continue_surveyed_route')
        with self.assertRaises(control.ControlError):control.command(self.site,obs,'follow_police')
        obs.update(police_direction='proceed',police_direction_source='authority')
        self.assertEqual(control.command(self.site,obs,'follow_police')['target'],'continue_surveyed_route')
    def test_native_bus_spawn_and_type_readback(self):
        class Bus:
            type_id='vehicle.bus'
            def __init__(self):self.destroyed=False
            def destroy(self):self.destroyed=True
        class Actors:
            def filter(self,_):return [type('Head',(),{'id':17})()]
        class World:
            def get_map(self):return type('Map',(),{'name':'TownSurvey'})()
            def get_actors(self):return Actors()
            def try_spawn_actor(self,_,transform):self.transform=transform;return Bus()
        class Carla:
            class Location:
                def __init__(self,**kwargs):self.coords=kwargs
            class Rotation:
                def __init__(self,**kwargs):self.angles=kwargs
            class Transform:
                def __init__(self,a,b):self.location=a;self.rotation=b
        world=World();out=scene.construct_native(self.site,self.root,world,Carla,type('BP',(),{'id':'vehicle.bus'})())
        self.assertEqual(world.transform.location.coords['x'],0.0)
        self.assertEqual(out['device_id'],17)
    def test_audit_missing_evidence_and_fixed_change(self):
        base={'map_sha256':'a','device_sha256':'b','route_sha256':'c','authority_sha256':'d',
              'bus_blueprint_id':'vehicle.bus','camera_profile':'four','duration_s':45,'device_id':17,
              'facing_approach_id':'north','police_direction':None,'aspect':'red','line_entry':False,
              'placement_source':'authority','nrs_307_context_source':'authority','original_trace_sha256':'e'}
        other=dict(base,line_entry=True)
        self.assertTrue(audit.audit_pair(base,other,'bus_line_behavior')['accepted_as_source_complete'])
        other['route_sha256']='bad'
        with self.assertRaisesRegex(audit.AuditError,'fixed'):audit.audit_pair(base,other,'bus_line_behavior')
        other['route_sha256']='c';other['original_trace_sha256']=''
        with self.assertRaisesRegex(audit.AuditError,'original'):audit.audit_pair(base,other,'bus_line_behavior')
        other=dict(base,police_direction='proceed',police_direction_source='authority')
        self.assertTrue(audit.audit_pair(base,other,'police_direction')['accepted_as_source_complete'])

if __name__=='__main__':unittest.main()

class DeliveryAuditTests(unittest.TestCase):
    def test_delivery_requires_video_original_and_stable_aspect(self):
        row={'frame':1,'aspect':'red','bus_front_signed_distance_m':2}
        rows=[row,dict(row,frame=2,bus_front_signed_distance_m=1),dict(row,frame=3,bus_front_signed_distance_m=-1)]
        m={'frames':rows,'device_id':17,'facing_approach_id':'north','bus_blueprint_id':'vehicle.bus',
           'map_sha256':'a','device_sha256':'b','route_sha256':'c','authority_sha256':'d',
           'original_trace_sha256':'e','four_view_video_sha256':'f','duration_s':45,
           'placement_source':'authority','nrs_307_context_source':'authority','case_id':'red_enter'}
        case={'case_id':'red_enter','duration_s':45,'device_aspect':'red','line_entry':True}
        self.assertTrue(audit.audit_delivery(m,case)['source_complete'])
        m['four_view_video_sha256']=''
        with self.assertRaisesRegex(audit.AuditError,'four_view_video'):audit.audit_delivery(m,case)
        m['four_view_video_sha256']='f';m['frames'][1]['aspect']='green'
        with self.assertRaisesRegex(audit.AuditError,'aspect changed'):audit.audit_delivery(m,case)
        m['frames'][1]['aspect']='red';m['frames'][2]['bus_front_signed_distance_m']=1
        with self.assertRaisesRegex(audit.AuditError,'line entry'):audit.audit_delivery(m,case)
