"""Focused CPU checks for Engineer-permitted front-direction construction."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from orientation_site import load_site
from orientation_measurement import measure
from orientation_native import control
from runner import selected_config

A='testing__C377875__LVMC-11-52-070__motor_vehicle_driver'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def make_site(root,suffix):
    activity,orientation=suffix.split('_',1);root=Path(root)
    records={'map':{'opendrive_sha256':'a'*64},'roadway':{'district':'business','jurisdiction':'city','highway_status':'reviewed_original','lawful_direction_status':'reviewed_original','lawful_traffic_vector_xy':[1,0]},'marking':{'marking_status':'reviewed_original','permission_indicated':True,'content_review':'original marking reviewed','governed_space_polygon_xy':[[0,0],[10,0],[10,10],[0,10]],'prop_blueprint_id':'static.prop.sign','prop_pose':{'x':2,'y':2,'z':0,'yaw_deg':0}},'authority':{'source':'signed Engineer record','determining_office':'City Traffic Engineer','permission_status':'reviewed_original','angle_parking_permitted':True,'permission_extent_polygon_xy':[[0,0],[10,0],[10,10],[0,10]]},'vehicle':{'source':'reviewed front identification','front_direction_status':'reviewed_original'},'purpose':{'activity_review':'reviewed_original','category':activity}}
    refs={}
    for name,value in records.items():
        path=root/(name+'.json');path.write_text(json.dumps(value)+'\n');refs[name]={'path':path.name,'sha256':sha(path)}
    site={'assignment_id':A,'case_id':A+'__'+suffix,'sources':refs,'target_xy':[5,5],'approach_xy':[5,20],'requested_activity':activity,'requested_orientation':orientation,'map_id':'Town01','road_id':1,'vehicle_blueprint_id':'vehicle.tesla.model3','approach_heading_degrees':-90,'target_heading_degrees':0 if orientation=='forward' else 180}
    path=root/'site.json';path.write_text(json.dumps(site)+'\n');return path

class SiteTests(unittest.TestCase):
    def test_both_exact_front_directions(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            path=make_site(tmp,'stand_forward');site,records=load_site(path,A+'__stand_forward');self.assertEqual(records['authority']['determining_office'],'City Traffic Engineer')
            path=make_site(tmp,'park_opposing');site,records=load_site(path,A+'__park_opposing');self.assertEqual(site['target_heading_degrees'],180)
    def test_reject_missing_engineer_determination(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            path=make_site(tmp,'stand_forward');data=json.loads((Path(tmp)/'authority.json').read_text());data['determining_office']='unknown';p=Path(tmp)/'authority.json';p.write_text(json.dumps(data)+'\n');site=json.loads(path.read_text());site['sources']['authority']['sha256']=sha(p);path.write_text(json.dumps(site)+'\n')
            with self.assertRaisesRegex(ValueError,'Engineer determination'):load_site(path,A+'__stand_forward')
    def test_reject_wrong_front(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            path=make_site(tmp,'stand_forward');site=json.loads(path.read_text());site['target_heading_degrees']=180;path.write_text(json.dumps(site)+'\n')
            with self.assertRaisesRegex(ValueError,'target front'):load_site(path,A+'__stand_forward')
    def test_reject_outside_permission(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            path=make_site(tmp,'stand_forward');site=json.loads(path.read_text());site['target_xy']=[20,20];path.write_text(json.dumps(site)+'\n')
            with self.assertRaisesRegex(ValueError,'permission extent'):load_site(path,A+'__stand_forward')

class MeasurementTests(unittest.TestCase):
    def packet(self,yaw):
        return {'source_kind':'diagnostic_native_shape','diagnostic_fixture':True,'assignment_id':A,'case_id':A+'__stand_forward','capture_source_sha256':'a','marking_source_sha256':'b','frame_map_sha256':'c','marking':{'marking_status':'reviewed_original','permission_indicated':True},'authority':{'determining_office':'City Traffic Engineer','permission_status':'reviewed_original','angle_parking_permitted':True},'roadway_source_review':'reviewed_original','lawful_direction_status':'reviewed_original','purpose_review':{'activity_review':'reviewed_original'},'lawful_traffic_vector_xy':[1,0],'frames':[{'frame':i,'halt_observed':True,'body_yaw_degrees':yaw} for i in range(3)]}
    def test_forward_and_opposing_observable(self):
        self.assertAlmostEqual(measure(self.packet(0))['front_vs_lawful_direction_mean_degrees'],0)
        self.assertAlmostEqual(measure(self.packet(180))['front_vs_lawful_direction_mean_degrees'],180)
    def test_reject_unreviewed_direction(self):
        packet=self.packet(0);packet['lawful_direction_status']='unreviewed'
        with self.assertRaisesRegex(ValueError,'lawful direction'):measure(packet)

class ControlTests(unittest.TestCase):
    def test_stand_depart_and_park_hold(self):
        command,state,_=control((0,0),0,0,(0,0),0,True,170,'stand',600)
        self.assertEqual(state,'depart')
        command,state,_=control((0,0),0,0,(0,0),0,True,170,'park',600)
        self.assertEqual(state,'hold');self.assertTrue(command['hand_brake'])
    def test_config_identity(self):self.assertEqual(selected_config()['law_id'],'LVMC-11-52-070')
if __name__=='__main__':unittest.main()
