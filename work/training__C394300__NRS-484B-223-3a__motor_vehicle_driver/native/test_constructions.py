"""CPU candidate distinction and measured-source trigger smoke tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from controller import PathController
from engineering import CANDIDATES,parameters
from trigger_evidence import evaluate
from survey import REQUESTS,survey


class ConstructionTests(unittest.TestCase):
    def test_native_survey_requests_bidirectional_center_and_rejects_driving(self):
        class Types:
            Bidirectional='bidirectional';Driving='driving'
        class Location:
            def __init__(self,**kwargs):self.x=kwargs['x'];self.y=kwargs['y']
        class Carla:pass
        Carla.LaneType=Types;Carla.Location=Location
        class Vector:
            def __init__(self,x,y):self.x=x;self.y=y
        class Transform:
            def __init__(self,x,y):self.x=x;self.y=y
            def get_forward_vector(self):return Vector(self.x,self.y)
        class Waypoint:
            def __init__(self,road,lane,kind,exit_lane):
                self.road_id=road;self.lane_id=lane;self.lane_type=kind
                self.lane_width=3.5;self.transform=Transform(0,-1) if exit_lane else Transform(1,0)
        class Mapping:
            wrong=False
            def get_waypoint(self,location,project_to_road,lane_type):
                name=next(n for n,(x,y,*_) in REQUESTS.items() if x==location.x and y==location.y)
                _,_,road,lane,kind=REQUESTS[name]
                result=Waypoint(road,lane,getattr(Types,kind),name.endswith('exit'))
                if self.wrong and name=='center_after_first_opportunity':result.lane_type=Types.Driving
                return result
        mapping=Mapping()
        self.assertTrue(survey(Carla,mapping)['native_lane_types_verified'])
        mapping.wrong=True
        with self.assertRaises(RuntimeError):survey(Carla,mapping)

    def test_four_distinct_law_preserving_requests_per_case(self):
        for case in ('controlled_1','controlled_2'):
            rows=[parameters(case,c) for c in CANDIDATES]
            self.assertEqual(len(rows),4)
            self.assertEqual({r['law_id'] for r in rows},{'NRS-484B-223-3a'})
            self.assertEqual(len({r['purpose_request'] for r in rows}),1)
            self.assertEqual(len({(r['route_start_x_m'],r['entry_advance_m'],
                r['controller_knobs'].lookahead_base_m,
                r['camera_plan'][1]['fov_deg']) for r in rows}),4)
            for row in rows:
                PathController(row['native_route_xy_m'],2.8,35,row['controller_knobs'])

    def test_measured_trigger_sources_and_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            rows=[{'native_frame':i,'source_kind':'synthetic_cpu',
                   'native_road_id':1,'native_lane_id':-1,
                   'native_center_xy_m':[-19+i,0],
                   'controller_request':{'route_error_m':1.0}} for i in range(5)]
            source=root/'native_samples.jsonl'
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertTrue(evaluate(root,'fallback1')['triggered'])
            self.assertTrue(evaluate(root,'fallback2')['triggered'])
            (root/'overview.mkv').write_bytes(b'synthetic-frame-fixture')
            audit={'review_scope':'synthetic_cpu',
                   'source_video_sha256':hashlib.sha256((root/'overview.mkv').read_bytes()).hexdigest(),
                   'frames':[{'native_frame':i,'center_lane_visible':i!=0,'body_visible':True}
                             for i in range(5)]}
            (root/'pixel_visibility_audit.json').write_text(json.dumps(audit))
            self.assertTrue(evaluate(root,'fallback3')['triggered'])
            audit['source_video_sha256']='0'*64
            (root/'pixel_visibility_audit.json').write_text(json.dumps(audit))
            with self.assertRaises(ValueError):evaluate(root,'fallback3')
            rows=[{'native_frame':i,'source_kind':'synthetic_cpu',
                   'native_road_id':1,'native_lane_id':-1,
                   'native_center_xy_m':[-25+i,0],
                   'controller_request':{'route_error_m':.1}} for i in range(16)]
            source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            audit={'review_scope':'synthetic_cpu',
                   'source_video_sha256':hashlib.sha256((root/'overview.mkv').read_bytes()).hexdigest(),
                   'frames':[{'native_frame':i,'center_lane_visible':True,'body_visible':True}
                             for i in range(16)]}
            (root/'pixel_visibility_audit.json').write_text(json.dumps(audit))
            for candidate in ('fallback1','fallback2','fallback3'):
                self.assertFalse(evaluate(root,candidate)['triggered'])


if __name__=='__main__':unittest.main()
