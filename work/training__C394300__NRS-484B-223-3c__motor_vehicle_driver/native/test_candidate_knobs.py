"""CPU checks for four distinct unselected after-turn constructions."""
import json
import math
import unittest
from pathlib import Path
from types import SimpleNamespace

from cameras import camera_plan
from controller import PathController
from engineering import TRIGGERS,parameters,trigger
from geometry import TARGET_FEET,open_drive
from runner import body_xy,check,map_survey


class CandidatesTest(unittest.TestCase):
    def test_authored_to_native_reflection_preserves_left_turn(self):
        for suffix in TARGET_FEET:
            plan=parameters(suffix,'primary')
            authored=plan['authored_route_xy_m']
            native=plan['native_route_xy_m']
            self.assertEqual(native,[[x,-y] for x,y in authored])
            self.assertGreater(native[0][1],native[399][1])
            self.assertGreater(native[-1][0],native[550][0])
            self.assertGreater(native[-1][1],native[550][1])
            self.assertEqual(plan['inbound_start_y_authored_m'],-45)
        xml=open_drive()
        self.assertIn('curvature="-0.14285714285714285"',xml)

    def test_native_survey_contract_uses_reflected_lane_side(self):
        class Location:
            def __init__(self,x,y,z):self.x,self.y,self.z=x,y,z
        def waypoint(x,y,road,lane,forward):
            return SimpleNamespace(road_id=road,lane_id=lane,lane_width=3.5,
                transform=SimpleNamespace(location=SimpleNamespace(x=x,y=y),
                    get_forward_vector=lambda:SimpleNamespace(x=forward[0],y=forward[1])))
        expected={(-71.75,25):waypoint(-71.75,25,4,-1,(0,-1)),
                  (-40,0):waypoint(-40,0,1,-1,(1,0)),
                  (-40,3.5):waypoint(-40,3.5,1,-2,(1,0))}
        mapping=SimpleNamespace(get_waypoint=lambda location,**kw:expected.get((location.x,location.y)))
        carla=SimpleNamespace(Location=Location,LaneType=SimpleNamespace(Driving='driving'))
        result=map_survey(carla,mapping,'a'*64)
        self.assertEqual(result['through_lane_native_xy_bounds_m'],[-66.5,1.75,90,5.25])
        self.assertFalse(result['native_center_lane_design_verified'])

    def test_four_distinct_knobs_preserve_comparison(self):
        for suffix in TARGET_FEET:
            with self.subTest(suffix=suffix):
                plans={name:parameters(suffix,name) for name in
                       ('primary','fallback1','fallback2','fallback3')}
                base=plans['primary']
                for plan in plans.values():
                    for key in ('law_id','cell_id','actor','duration_s','rate_hz',
                                'comparison_commanded_distance_ft','requested_movement'):
                        self.assertEqual(plan[key],base[key])
                self.assertNotEqual(plans['fallback1']['native_route_xy_m'],base['native_route_xy_m'])
                self.assertEqual(plans['fallback1']['controller_knobs'],base['controller_knobs'])
                self.assertEqual(plans['fallback1']['cameras'],base['cameras'])
                self.assertEqual(plans['fallback2']['native_route_xy_m'],base['native_route_xy_m'])
                self.assertNotEqual(plans['fallback2']['controller_knobs'],base['controller_knobs'])
                self.assertEqual(plans['fallback2']['cameras'],base['cameras'])
                self.assertEqual(plans['fallback3']['native_route_xy_m'],base['native_route_xy_m'])
                self.assertEqual(plans['fallback3']['controller_knobs'],base['controller_knobs'])
                self.assertNotEqual(plans['fallback3']['cameras'],base['cameras'])

    def test_triggers_require_measured_original_sources(self):
        self.assertEqual(len(TRIGGERS),3)
        self.assertTrue(trigger('fallback1',{'source':TRIGGERS['fallback1']['source'],
            'inbound_body_containment_fraction':.99,'turn_completion_time_s':3.5}))
        self.assertFalse(trigger('fallback1',{'source':TRIGGERS['fallback1']['source'],
            'inbound_body_containment_fraction':1,'turn_completion_time_s':3.5}))
        self.assertTrue(trigger('fallback2',{'source':TRIGGERS['fallback2']['source'],
            'max_premerge_route_error_m':.36}))
        self.assertFalse(trigger('fallback2',{'source':TRIGGERS['fallback2']['source'],
            'max_premerge_route_error_m':.35}))
        self.assertTrue(trigger('fallback3',{'source':TRIGGERS['fallback3']['source'],
            'marking_and_body_visible_fraction':.94}))
        self.assertFalse(trigger('fallback3',{'source':TRIGGERS['fallback3']['source'],
            'marking_and_body_visible_fraction':.95}))
        with self.assertRaisesRegex(ValueError,'source missing'):
            trigger('fallback3',{'marking_and_body_visible_fraction':.94})

    def test_observed_pose_controller_commands_are_bounded(self):
        for name in ('primary','fallback1','fallback2','fallback3'):
            plan=parameters('below_50_ft',name)
            route=plan['native_route_xy_m']
            controller=PathController(route,2.7,35,plan['controller_knobs'])
            command=controller.step(position_xy_m=tuple(route[0]),yaw_rad=-math.pi/2,
                                    speed_mps=0,dt_s=.05)
            self.assertGreaterEqual(command['route_error_m'],0)
            self.assertLessEqual(abs(command['steer']),.7)
            self.assertLessEqual(command['throttle'],1)

    def test_original_body_corners_are_perimeter_ordered(self):
        points=[SimpleNamespace(x=x,y=y) for x,y in
                ((2,1),(-2,-1),(2,-1),(-2,1),(2,1),(-2,-1))]
        actor=SimpleNamespace(get_transform=lambda:None,
            bounding_box=SimpleNamespace(get_world_vertices=lambda transform:points))
        polygon=body_xy(actor)
        area=sum(polygon[i][0]*polygon[(i+1)%4][1]-
                 polygon[(i+1)%4][0]*polygon[i][1] for i in range(4))/2
        self.assertEqual(area,8)

    def test_camera_profile_and_config(self):
        cameras=camera_plan('primary')
        self.assertEqual([(c['width'],c['height']) for c in cameras],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])
        here=Path(__file__).parent
        config_path=here/'config.json' if (here/'config.json').is_file() else here.parent/'config.json'
        config=json.loads(config_path.read_text())
        self.assertEqual(set(config['mandatory_channels']),set(config['required_atoms'])|
                         {'native_body_pose_control','camera_frame_join'})
        self.assertFalse(check(config)['physical_success_claimed'])


if __name__=='__main__':unittest.main()
