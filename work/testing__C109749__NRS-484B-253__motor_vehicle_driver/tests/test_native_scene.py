import importlib.util
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('c109749_native_scene',ROOT/'native_scene.py')
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)


def point(x,y):
    return NS(x=x,y=y,z=0.0)


def waypoint(x,y,junction=None):
    return NS(transform=NS(location=point(x,y)),get_junction=lambda:junction)


class Actor:
    def __init__(self,ident,x,y,vx):
        self.id,self.x,self.y,self.vx=ident,x,y,vx
        self.bounding_box=NS(get_world_vertices=lambda transform:[
            point(self.x+dx,self.y+dy) for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]])
    def get_transform(self):return NS(location=point(self.x,self.y))
    def get_velocity(self):return NS(x=self.vx,y=0,z=0)


def selected():
    junction=NS(id=17,bounding_box=NS(location=point(0,0),
             extent=NS(x=5.0,y=4.0),rotation=NS(yaw=0)))
    return {'junction_id':17,
            'ego':{'outside':waypoint(0,-40),'entry':waypoint(0,-4,junction)},
            'oncoming':{'outside':waypoint(40,0),'entry':waypoint(4,0,junction)}}


class NativeSceneTests(unittest.TestCase):
    def test_district_packet_binds_native_junction_to_source_polygon(self):
        context=scene.junction_context(selected())
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'district.json'
            packet_path=Path(directory)/'packet.json'
            document={'format':'c109749-district-polygon-source-v1',
                      'native_map_name':'Town01',
                      'district_class':'business_or_residential',
                      'polygon_xy_m':[[-10,-10],[10,-10],[10,10],[-10,10]],
                      'source_origin':'synthetic test polygon',
                      'review_basis':'fixture checks geometry and binding only',
                      'diagnostic_only':True}
            source.write_text(json.dumps(document))
            packet={'format':'c109749-district-site-review-v1',
                    'review_status':'candidate_reviewed',
                    'native_map_name':'Town01','native_junction_id':17,
                    'junction_polygon_xy_m':context['intersection_polygon_xy_m'],
                    'district_source':{'path':source.name,
                                       'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}
            packet_path.write_text(json.dumps(packet))
            result=scene.verify_district_site_packet(context,'Town01',packet_path)
            self.assertTrue(result['diagnostic_only'])
            self.assertFalse(result['physical_district_verified'])
            selected_context=scene.junction_context(selected(),native_map_name='Town01',
                                                    district_packet_path=packet_path)
            self.assertEqual(selected_context['district_site_review'],result)
            with self.assertRaisesRegex(ValueError,'selected Native junction'):
                scene.verify_district_site_packet(context,'Town02',packet_path)
            packet['native_junction_id']=18
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,'selected Native junction'):
                scene.verify_district_site_packet(context,'Town01',packet_path)
            packet['native_junction_id']=17
            packet_path.write_text(json.dumps(packet))
            source.write_text(source.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                scene.verify_district_site_packet(context,'Town01',packet_path)

    def test_district_packet_rejects_polygon_outside_junction(self):
        context=scene.junction_context(selected())
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'district.json'
            packet_path=Path(directory)/'packet.json'
            source.write_text(json.dumps({'format':'c109749-district-polygon-source-v1',
                'native_map_name':'Town01','district_class':'business_or_residential',
                'polygon_xy_m':[[20,20],[30,20],[30,30],[20,30]],
                'source_origin':'synthetic test polygon','review_basis':'fixture',
                'diagnostic_only':True}))
            packet_path.write_text(json.dumps({'format':'c109749-district-site-review-v1',
                'review_status':'candidate_reviewed','native_map_name':'Town01',
                'native_junction_id':17,
                'junction_polygon_xy_m':context['intersection_polygon_xy_m'],
                'district_source':{'path':source.name,
                    'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}))
            with self.assertRaisesRegex(ValueError,'does not cover'):
                scene.verify_district_site_packet(context,'Town01',packet_path)

    def test_opposing_waypoint_direction_and_sourced_geometry(self):
        context=scene.junction_context(selected())
        self.assertEqual(context['native_junction_id'],17)
        self.assertEqual(context['oncoming_direction_xy'],[-1.0,0.0])
        self.assertEqual(context['intersection_polygon_xy_m'][0],[-5.0,-4.0])

    def test_measured_initial_yield_and_then_clearance(self):
        chosen=selected();context=scene.junction_context(chosen)
        ego=Actor(10,0,-7,3)
        oncoming=Actor(11,2,0,-3)
        inside=scene.control_inputs(chosen,ego,oncoming,context)
        self.assertTrue(inside['oncoming_in_intersection'])
        self.assertTrue(inside['seen_oncoming_inside'])
        self.assertFalse(inside['oncoming_cleared'])
        oncoming.x=-15
        clear=scene.control_inputs(chosen,ego,oncoming,context,
                                   seen_oncoming_inside=inside['seen_oncoming_inside'])
        self.assertFalse(clear['oncoming_in_intersection'])
        self.assertTrue(clear['oncoming_cleared'])
        self.assertGreater(clear['distance_to_hold_m'],0)

    def test_no_clearance_claim_before_observed_presence(self):
        chosen=selected();context=scene.junction_context(chosen)
        result=scene.control_inputs(chosen,Actor(10,0,-30,3),Actor(11,-15,0,-3),context)
        self.assertFalse(result['oncoming_cleared'])

    def test_degenerate_opposing_approach_rejected(self):
        chosen=selected()
        chosen['oncoming']['entry']=waypoint(40,0,chosen['ego']['entry'].get_junction())
        with self.assertRaisesRegex(ValueError,'approach direction'):
            scene.junction_context(chosen)
