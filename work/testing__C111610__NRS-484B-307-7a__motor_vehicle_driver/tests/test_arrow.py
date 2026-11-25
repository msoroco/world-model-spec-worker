import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
scene=module('native_arrow'); control=module('turn_control'); audit=module('comparison_audit')
POLY=[[-3,-3],[3,-3],[3,3],[-3,3]]
CROSS=[[3,-3],[6,-3],[6,3],[3,3]]
class ArrowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        refs=[]
        for name in ('map','signal','route','crosswalk'):
            p=self.root/(name+'.json'); p.write_text(json.dumps({'name':name}))
            refs.append({'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        self.site={'cell_id':'C111610','actor':'motor_vehicle_driver','original_sources':refs,'map_source_path':'map.json','signal_source_path':'signal.json','route_source_path':'route.json','crosswalk_source_path':'crosswalk.json','native_map_name':'TownTest','official_head_id':'17','ego_approach_id':'north','facing_relation':True,'arrow_movement':'left','ego_route_xy':[[0,-8],[0,0],[-8,0]],'intersection_polygon_xy':POLY,'adjacent_crosswalk_polygon_xy':CROSS,'signal_source_mode':'native_head_plus_external_aspect_packet','spawn_z_m':0.5,'ego_yaw_deg':90,'other_yaw_deg':0,'other_spawn_xy':[4,0],'stop_line_xy':[0,-4],'approach_control_radius_m':5,'approach_throttle':0.2,'yield_brake':0.6,'turn_throttle':0.1}
    def tearDown(self): self.tmp.cleanup()
    def event(self, users=None, aspects=None, movement='left'):
        users=users or []; aspects=aspects or ['flashing_yellow_turn_arrow']
        rows=[]
        for i,xy in enumerate(([0,-8],[0,0],[-8,0])):
            rows.append({'frame':i,'official_head_id':'17','facing_approach_id':'north','lit_aspects':aspects if i!=1 else [],'arrow_movement':'left','ego_movement':movement,'ego_xy':xy,'other_users':users})
        p=self.root/'events.json'; p.write_text(json.dumps(rows));return {'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def test_site_and_geometry(self):
        self.assertTrue(scene.verify_site(self.site,self.root))
        self.assertTrue(scene.in_polygon([3,0],POLY))
        self.site['arrow_movement']='right'
        with self.assertRaises(scene.ArrowError): scene.verify_site(self.site,self.root)
    def test_source_hash_and_facing(self):
        self.site['facing_relation']=False
        with self.assertRaises(scene.ArrowError): scene.verify_site(self.site,self.root)
        self.site['facing_relation']=True
        (self.root/'signal.json').write_text('{}')
        with self.assertRaises(scene.ArrowError): scene.verify_site(self.site,self.root)
    def test_original_measurement(self):
        u={'id':'p1','kind':'pedestrian','xy':[4,0],'lawful_presence_source':'crossing-log'}
        result=scene.measure_original(self.site,self.root,self.event([u]))
        self.assertEqual(result['records'][0]['other_users'][0]['region'],'adjacent_crosswalk')
        self.assertEqual(result['lawful_presence_verdict'],None)
        u.pop('lawful_presence_source')
        with self.assertRaises(scene.ArrowError): scene.measure_original(self.site,self.root,self.event([u]))
    def test_wrong_signal_and_movement_rejected(self):
        with self.assertRaises(scene.ArrowError): scene.measure_original(self.site,self.root,self.event(aspects=['green']))
        with self.assertRaises(scene.ArrowError): scene.measure_original(self.site,self.root,self.event(movement='straight'))
    def test_control_hold_and_turn(self):
        packet={'official_head_id':'17','facing_approach_id':'north','lit_aspects':['flashing_yellow_turn_arrow'],'ego_movement':'left','frame':2,'ego_xy':[0,-4],'other_users':[{'region':'adjacent_crosswalk'}]}
        self.assertEqual(control.command(self.site,packet,'yield_to_present')['target'],'hold_before_entry')
        packet['other_users']=[]
        self.assertEqual(control.command(self.site,packet,'yield_to_present')['target'],'turn_route')
        packet['lit_aspects']=[]
        with self.assertRaises(control.ControlError): control.command(self.site,packet,'yield_to_present')
    def test_concurrent_control_requires_display_and_distinct_route(self):
        packet={'official_head_id':'17','facing_approach_id':'north',
                'lit_aspects':['flashing_yellow_turn_arrow'],
                'ego_movement':'straight','concurrently_permitted_movement':'straight',
                'frame':2,'ego_xy':[0,-4],'other_users':[]}
        with self.assertRaisesRegex(control.ControlError,'indication or route'):
            control.command(self.site,packet,'yield_to_present')
        self.site['concurrent_route_xy']=[[0,-8],[0,0],[0,8]]
        packet['concurrent_indications']=['straight_green']
        with self.assertRaisesRegex(control.ControlError,'indication or route'):
            control.command(self.site,packet,'yield_to_present')
        packet['concurrent_permission_source']='reviewed-concurrent-controller'
        self.assertEqual(control.command(self.site,packet,'yield_to_present')['target'],
                         'concurrent_route')
    def test_native_spawn_and_cleanup(self):
        class Actor:
            def __init__(self, ident): self.id=ident; self.destroyed=False
            def destroy(self): self.destroyed=True
        class Head(Actor): pass
        class Actors:
            def filter(self, pattern): return [Head(17)]
        class World:
            def __init__(self): self.spawned=[]; self.fail_second=False
            def get_map(self):
                class Map:
                    name='TownTest'
                    def get_waypoint(self, location):
                        point=type('Point',(),{'x':location['x'],'y':location['y']})()
                        return type('Waypoint',(),{'transform':type('Transform',(),{'location':point})()})()
                    def get_crosswalks(self): return [type('Point',(),{'x':x,'y':y})()
                                                       for x,y in ((3,-3),(6,-3),(6,3),(3,3))]
                return Map()
            def get_actors(self): return Actors()
            def try_spawn_actor(self, blueprint, transform):
                if self.fail_second and self.spawned: return None
                actor=Actor(len(self.spawned)+1); self.spawned.append(actor); return actor
        class Carla:
            @staticmethod
            def Location(**kwargs): return kwargs
            @staticmethod
            def Rotation(**kwargs): return kwargs
            @staticmethod
            def Transform(location,rotation): return (location,rotation)
        world=World()
        packet=scene.construct_native(self.site,self.root,world,Carla(),'vehicle','walker','pedestrian')
        self.assertEqual(len(packet['actors']),2)
        self.assertEqual(len(world.spawned),2)
        world=World(); world.fail_second=True
        with self.assertRaises(scene.ArrowError): scene.construct_native(self.site,self.root,world,Carla(),'vehicle','walker','pedestrian')
        self.assertTrue(world.spawned[0].destroyed)
    def test_concurrent_movement_requires_surveyed_distinct_route(self):
        self.site['case_id']='testing__C111610__NRS-484B-307-7a__motor_vehicle_driver__arrow_concurrent_movement'
        self.site['concurrent_route_xy']=[[0,-8],[0,0],[0,8]]
        self.site['concurrent_route_source_path']='concurrent_route.json'
        with self.assertRaisesRegex(scene.ArrowError,'route source missing'):
            scene.verify_site(self.site,self.root)
        route=self.root/'concurrent_route.json'
        route.write_text(json.dumps({'route_xy':self.site['concurrent_route_xy']}))
        self.site['original_sources'].append({'path':route.name,'sha256':hashlib.sha256(route.read_bytes()).hexdigest()})
        self.assertTrue(scene.verify_site(self.site,self.root))
        route.write_text(json.dumps({'route_xy':[[0,-8],[1,0],[0,8]]}))
        with self.assertRaisesRegex(scene.ArrowError,'hash mismatch'):
            scene.verify_site(self.site,self.root)
    def test_comparison_rejects_missing_source_and_wrong_region(self):
        def rec(suffix,user=[]):
            return {'case_suffix':suffix,'map_sha256':'a','route_source_sha256':'b','crosswalk_source_sha256':'c','signal_source_sha256':'d','duration_frames':3,'camera_profile_sha256':'e','official_head_id':'17','ego_approach_id':'north','concurrent_indications':[],'ego_movement':'left','records':[{'lit_aspects':['flashing_yellow_turn_arrow'] if i!=1 else [],'other_users':user} for i in range(3)]}
        left=rec('arrow_clear');right=rec('arrow_ped_crosswalk',[{'kind':'pedestrian','region':'adjacent_crosswalk'}])
        self.assertTrue(audit.audit('pedestrian_crosswalk',left,right)['source_history_checked'])
        right['records']=[]
        with self.assertRaises(audit.AuditError): audit.audit('pedestrian_crosswalk',left,right)
        right=rec('arrow_ped_crosswalk',[{'kind':'pedestrian','region':'intersection'}])
        with self.assertRaises(audit.AuditError): audit.audit('pedestrian_crosswalk',left,right)
if __name__=='__main__': unittest.main()
