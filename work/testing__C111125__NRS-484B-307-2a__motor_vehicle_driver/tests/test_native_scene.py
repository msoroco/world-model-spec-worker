import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
native=module('native_scene');audit=module('comparison_audit')

class Actor:
    def __init__(self,aid=1): self.id=aid;self.destroyed=False
    def get_state(self): return type('State',(),{'name':'Green'})()
    def destroy(self): self.destroyed=True
class Actors:
    def filter(self,pattern): return [Actor('head-7')]
class World:
    def __init__(self):self.calls=[];self.succeed=True
    def get_map(self):return type('Map',(),{'name':'NativeCrossing'})()
    def get_actors(self):return Actors()
    def try_spawn_actor(self,bp,transform):
        self.calls.append((bp,transform))
        return Actor(len(self.calls)) if self.succeed else None
class Carla:
    @staticmethod
    def Location(**kw):return kw
    @staticmethod
    def Rotation(**kw):return kw
    @staticmethod
    def Transform(a,b):return (a,b)

def ref(base,name,data):
    p=base/name;p.write_text(json.dumps(data))
    return {'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def site(base):
    refs=[ref(base,n,{'original':n}) for n in ('map.json','signal.json','route.json','crosswalk.json')]
    return {'cell_id':'C111125','actor':'motor_vehicle_driver','original_sources':refs,'map_source_path':'map.json','signal_source_path':'signal.json','route_source_path':'route.json','crosswalk_source_path':'crosswalk.json','official_head_id':'head-7','ego_approach_id':'north','facing_relation':True,'ego_route_xy':[[-4,0],[0,0],[4,0]],'straight_tolerance_m':0.1,'intersection_polygon_xy':[[-1,-1],[1,-1],[1,1],[-1,1]],'adjacent_crosswalk_polygon_xy':[[-1,2],[1,2],[1,3],[-1,3]],'native_map_name':'NativeCrossing','initial_lit_aspects':['circular_green'],'spawn_z_m':0.3,'approach_yaw_deg':0,'other_user_spawn_xy':[0,2.5]}

class NativeTests(unittest.TestCase):
    def test_source_gated_spawn_and_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);s=site(base);w=World()
            out=native.construct_native(s,base,w,Carla,'vehicle.ego','walker.other','pedestrian')
            self.assertEqual(len(out['actors']),2);self.assertEqual(len(w.calls),2)
            self.assertEqual(w.calls[1][1][0]['y'],2.5)
            s['initial_lit_aspects']=['green_arrow']
            with self.assertRaisesRegex(native.SourceError,'sole circular green'):
                native.construct_native(s,base,w,Carla,'vehicle.ego')
    def test_site_rejects_turn_and_stale_source(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);s=site(base);self.assertTrue(native.verify_site(s,base))
            s['ego_route_xy'][1]=[0,3]
            with self.assertRaisesRegex(native.SourceError,'route turns'):
                native.verify_site(s,base)
            s=site(base);(base/'map.json').write_text('{}')
            with self.assertRaisesRegex(native.SourceError,'source hash mismatch'):
                native.verify_site(s,base)
    def test_exhibition_uses_original_position_not_later_position(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);s=site(base)
            def row(frame,ego,other):
                return {'frame':frame,'official_head_id':'head-7','facing_approach_id':'north','lit_aspects':['circular_green'],'ego_xy':ego,'other_users':[{'id':'ped-2','kind':'pedestrian','xy':other,'lawful_presence_source':'original-lawful-context.json'}]}
            r=ref(base,'events.json',[row(1,[-4,0],[0,4]),row(2,[0,0],[0,2.5]),row(3,[4,0],[0,2.5])])
            out=native.measure_attempt(s,base,r)
            self.assertEqual(out['exhibition']['other_users'][0]['region'],'outside')
            self.assertEqual(out['records'][1]['other_users'][0]['region'],'adjacent_crosswalk')
            s['official_head_id']='wrong'
            with self.assertRaisesRegex(native.SourceError,'signal identity'):
                native.measure_attempt(s,base,r)
    def test_comparison_audit_rejects_missing_and_changed_fixed_source(self):
        base={'map_sha256':'a','signal_source_sha256':'b','route_source_sha256':'c','crosswalk_source_sha256':'d','camera_profile_sha256':'e','duration_frames':3,'official_head_id':'head-7','ego_approach_id':'north','green_frames':3,'lawful_presence_verdict':None,'right_of_way_verdict':None}
        left={**base,'case_suffix':'green_clear','exhibition':{'other_users':[]}}
        right={**base,'case_suffix':'green_pedestrian_present','exhibition':{'other_users':[{'region':'adjacent_crosswalk'}]}}
        self.assertTrue(audit.audit_pair('crosswalk_pedestrian_yield',left,right)['exhibition_checked'])
        with self.assertRaisesRegex(audit.ComparisonError,'fixed condition'):
            audit.audit_pair('crosswalk_pedestrian_yield',left,{**right,'map_sha256':'other'})
        with self.assertRaisesRegex(audit.ComparisonError,'original exhibition'):
            audit.audit_pair('crosswalk_pedestrian_yield',left,{**right,'exhibition':None})
        with self.assertRaisesRegex(audit.ComparisonError,'other user region'):
            audit.audit_pair('crosswalk_pedestrian_yield',left,{**right,'exhibition':{'other_users':[{'region':'outside'}]}})

if __name__=='__main__':unittest.main()
