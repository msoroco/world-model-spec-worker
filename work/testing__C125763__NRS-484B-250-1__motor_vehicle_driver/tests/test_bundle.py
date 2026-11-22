import json
import unittest
from pathlib import Path
from runner import ASSIGNMENT, CASE_IDS, load_config

class BundleTest(unittest.TestCase):
    def test_exact_identity_and_four_cameras(self):
        config,scene=load_config(Path('config.json'))
        self.assertEqual(config['assignment_id'],ASSIGNMENT)
        self.assertEqual(CASE_IDS,{config['selected_case_id']})
        self.assertEqual(config['frames'],900)
        self.assertEqual(config['duration_s'],45)
        self.assertEqual(set(scene['camera_poses']),{'overview','approach','reference_corner','driver_reference'})
        self.assertEqual(scene['yield_sign']['native_id'],17)
        self.assertNotEqual(scene['approaches']['ego']['highway_id'],scene['approaches']['other']['highway_id'])
        self.assertNotEqual(scene['approaches']['ego']['spawn_pose'],scene['approaches']['other']['spawn_pose'])
        self.assertEqual(scene['approaches']['other']['spawn_pose'][:2],scene['approaches']['other']['route_xy_m'][0])

    def test_capture_row_matches_saved_measurement_schema(self):
        import io
        from types import SimpleNamespace as NS
        from capture_sources import record_sample
        from runner import _context
        config,scene=load_config(Path('config.json'))
        def actor(ident,road,x):
            vertices=[NS(x=x,y=-1),NS(x=x-2,y=-1),NS(x=x-2,y=1),NS(x=x,y=1)]
            pose=NS(location=NS(x=x,y=0,z=0),rotation=NS(yaw=0))
            return NS(id=ident,bounding_box=NS(get_world_vertices=lambda p:vertices),
                      get_transform=lambda:pose,get_location=lambda:pose.location,
                      get_velocity=lambda:NS(x=3,y=0,z=0))
        ego,other=actor(1,1,-20),actor(2,2,-15)
        world_map=NS(get_waypoint=lambda loc,project_to_road: NS(road_id=1 if loc.x==-20 else 2,lane_id=1,is_junction=False))
        frame_map=NS(append=lambda frame,time: {'video_frame':0,'carla_frame':frame,'time_s':time})
        stream=io.StringIO()
        snap=NS(frame=100,time=0,timestamp=NS(elapsed_seconds=1.0))
        mapped,row=record_sample(frame_map,stream,snap,world_map,ego,other,
                                 NS(id=17),{name:100 for name in scene['camera_poses']},scene)
        self.assertEqual(row['native_yield_sign_id'],_context(scene)['native_yield_sign_id'])
        self.assertEqual(row['ego']['speed_mps'],3)
        self.assertGreater(row['ego']['distance_to_intersection_m'],0)
        self.assertEqual(json.loads(stream.getvalue()),row)
        self.assertEqual(mapped['carla_frame'],100)
