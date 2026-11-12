import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE))
from backing_corridor import verify
from backing_source_capture import BackingSourceRecorder
from backing_safety_measurement import measure
from runner import check_traffic_placement,PREFIX

class Actor:
    def __init__(self, ident, x, speed):
        self.id=ident;self.x=x;self.speed=speed
        self.bounding_box=SimpleNamespace(extent=SimpleNamespace(x=1.,y=.7))
    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x,y=10.),
            get_forward_vector=lambda:SimpleNamespace(x=1.,y=0.))
    def get_velocity(self):return SimpleNamespace(x=self.speed,y=0.)

class NativeComponents(unittest.TestCase):
    def test_exact_clearance_placement(self):
        corridor={'start_xy':[20,1.75],'other_vehicle_xy':[8,1.75]}
        self.assertEqual(check_traffic_placement(corridor,PREFIX+'backing_clear_vehicle'),12.)
        with self.assertRaisesRegex(ValueError,'initial distance'):
            check_traffic_placement(corridor,PREFIX+'backing_near_vehicle')
        corridor['other_vehicle_xy']=[9.5,1.75]
        self.assertEqual(check_traffic_placement(corridor,PREFIX+'backing_near_vehicle'),10.5)
        with self.assertRaisesRegex(ValueError,'initial distance'):
            check_traffic_placement(corridor,PREFIX+'backing_clear_vehicle')
    def corridor(self):
        return {'format':'worker-native-backing-corridor-v1',
                'verified_intersection':True,'reviewer':'test reviewer',
                'evidence_reference':'reviewed source annotation',
                'map_name':'TestMap','opendrive_sha256':hashlib.sha256(b'<OpenDRIVE/>').hexdigest(),
                'intersection_polygon_xy':[[0,0],[20,0],[20,20],[0,20]],
                'start_xy':[16,10],'end_xy':[7,10],
                'other_vehicle_xy':[11,10],'other_vehicle_purpose':'travel through intersection',
                'other_vehicle_road_id':4,'other_vehicle_lane_id':-1}
    def test_corridor_positive_and_wrong_map(self):
        world_map=SimpleNamespace(name='TestMap',to_opendrive=lambda:'<OpenDRIVE/>')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'corridor.json';p.write_text(json.dumps(self.corridor()))
            result=verify(world_map,p,(1,0))
            self.assertEqual(result['end_xy'],(7.,10.))
            source=self.corridor();source['opendrive_sha256']='0'*64;p.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'map/OpenDRIVE'):verify(world_map,p,(1,0))
    def test_forward_path_and_outside_other_rejected(self):
        world_map=SimpleNamespace(name='TestMap',to_opendrive=lambda:'<OpenDRIVE/>')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'corridor.json';source=self.corridor();source['end_xy']=[19,10];p.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'bounded reverse'):verify(world_map,p,(1,0))
            source=self.corridor();source['other_vehicle_xy']=[30,10];p.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'outside'):verify(world_map,p,(1,0))
    def test_original_capture_feeds_measurement(self):
        with tempfile.TemporaryDirectory() as d:
            ego=Actor(10,16,-1);other=Actor(20,11,1)
            context={'participants':{'20':{'kind':'vehicle',
                'position_motion_purpose_source':'reviewed corridor plus Native transform and velocity',
                'highway_use_source':'Native road/lane readback and reviewed annotation',
                'purpose':'travel through intersection'}},
                'corridor_source_sha256':'a'*64}
            recorder=BackingSourceRecorder(d,ego,[other],context)
            for index in range(3):
                recorder.append(100+index,.05*index);ego.x-=.5;other.x+=.1
            recorder.contact(101,20)  # Event callbacks can arrive after frame capture.
            hashes=recorder.close()
            observed=measure(Path(d)/'backing_motion.jsonl',Path(d)/'backing_contacts.jsonl',Path(d)/'backing_context.json')
            self.assertEqual(observed['backing_onset_frame'],100)
            self.assertEqual(observed['contact_frames_during_backing'],[101])
            self.assertEqual(observed['sources'],hashes)
            self.assertIsNone(observed['reasonable_safety_legal_judgment'])
    def test_unknown_contact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ego=Actor(10,16,-1);other=Actor(20,11,1)
            context={'participants':{'20':{'kind':'vehicle','position_motion_purpose_source':'Native readback','highway_use_source':'reviewed road'}}}
            recorder=BackingSourceRecorder(d,ego,[other],context)
            with self.assertRaisesRegex(ValueError,'unknown actor'):recorder.contact(1,30)
            recorder.close()

if __name__=='__main__':unittest.main()
