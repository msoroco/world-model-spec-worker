import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('condition_capture',ROOT/'condition_capture.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
MEASURE_SPEC=importlib.util.spec_from_file_location('conditions_measurements',ROOT/'conditions_measurements.py')
MEASURE=importlib.util.module_from_spec(MEASURE_SPEC);MEASURE_SPEC.loader.exec_module(MEASURE)


class Location:
    def __init__(self, *, x, y, z):self.x,self.y,self.z=x,y,z


class ConditionCaptureTests(unittest.TestCase):
    def packet(self, root):
        text='Observed pavement condition from original site review.\n'
        (root/'surface.txt').write_text(text)
        return {'review_status':'reviewed_native_surface','native_map_id':'FixtureMap','road_id':7,'reviewer':'test fixture reviewer',
                'review_basis':'test fixture declaration','surface':'wet',
                'source':{'path':'surface.txt','sha256':hashlib.sha256(text.encode()).hexdigest()}}

    def test_source_binding_and_frame_join_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            review=MODULE.validate_surface_packet(self.packet(root),root)
            waypoint=NS(road_id=7,lane_id=-1,lane_width=3.2,
                        transform=NS(rotation=NS(yaw=0)),
                        next=lambda distance:[NS(transform=NS(rotation=NS(yaw=5)))])
            native_map=NS(get_waypoint=lambda location,project_to_road:waypoint)
            world=NS(get_map=lambda:native_map,
                     cast_ray=lambda eye,target:[NS(location=Location(x=60,y=0,z=1.5))],
                     get_weather=lambda:NS(precipitation=75))
            ego=NS(id=10,get_location=lambda:Location(x=0,y=0,z=0),
                   get_velocity=lambda:NS(x=10,y=0,z=0),bounding_box=NS(extent=NS(x=2)))
            lead=NS(id=20,get_location=lambda:Location(x=25,y=0,z=0),
                    get_velocity=lambda:NS(x=7,y=0,z=0),bounding_box=NS(extent=NS(x=2)))
            snapshot=NS(frame=100,timestamp=NS(elapsed_seconds=5.0))
            row=MODULE.sample_frame(world,ego,lead,snapshot,review,Location(x=0,y=0,z=1.5),
                                    (1,0,0),map_source='Native map',ray_source='Native ray')
            self.assertEqual(row['frame'],100)
            self.assertEqual(row['surrounding_traffic'][0]['longitudinal_body_gap_m'],21)
            self.assertEqual(row['sight_distance_m'],60)
            self.assertEqual(row['surface'],'wet')
            self.assertFalse(row['physical_surface_verified'])
            self.assertGreater(row['curvature_per_m'],0)
            context={'native_map_id':'FixtureMap','ego_actor_id':10,'road_id':7,'lane_id':-1,
                     'road_surface_source':review['source'],'lane_width_source':'Native waypoint',
                     'traffic_source':'Native actor','weather_source':'Native weather',
                     'sight_source':'Native ray','curvature_source':'Native waypoint',
                     'braking_model_source':'declared engineering model',
                     'diagnostic_reaction_time_s':1.0,
                     'diagnostic_braking_deceleration_mps2':5.0}
            (root/'road_context.json').write_text(json.dumps(context)+'\n')
            second=dict(row,frame=101,time_s=5.05)
            (root/'condition_history.jsonl').write_text(json.dumps(row)+'\n'+json.dumps(second)+'\n')
            frames=[{'video_frame':i,'carla_frame':item['frame'],'time_s':item['time_s']}
                    for i,item in enumerate((row,second))]
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(item)+'\n' for item in frames))
            analyzed=MEASURE.analyze(root)
            self.assertEqual(analyzed['samples'][0]['sight_distance_m'],60)
            self.assertFalse(analyzed['engineering_model']['legal_threshold'])
            (root/'surface.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'hash changed'):
                MODULE.validate_surface_packet(self.packet_hash_only(root),root)

    def packet_hash_only(self, root):
        text='Observed pavement condition from original site review.\n'
        return {'review_status':'reviewed_native_surface','native_map_id':'FixtureMap','road_id':7,'reviewer':'fixture reviewer',
                'review_basis':'fixture declaration','surface':'wet',
                'source':{'path':'surface.txt','sha256':hashlib.sha256(text.encode()).hexdigest()}}

    def test_diagnostic_and_missing_surface_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=self.packet(root)
            packet['review_status']='synthetic diagnostic'
            with self.assertRaisesRegex(ValueError,'review packet required'):
                MODULE.validate_surface_packet(packet,root)
            packet=self.packet(root)
            (root/'surface.txt').unlink()
            with self.assertRaisesRegex(ValueError,'missing'):
                MODULE.validate_surface_packet(packet,root)


if __name__=='__main__':unittest.main()
