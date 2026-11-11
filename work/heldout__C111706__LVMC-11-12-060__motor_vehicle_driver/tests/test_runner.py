import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import check_config, resolve_survey, steer_toward
from fire_station_camera_capture import plans


def survey(reverse=False):
    def ref(road,lane,s):return {'road_id':road,'lane_id':lane,'s':s}
    before,after=(8,-8) if reverse else (-8,8)
    return {'map_name':'source-bound-test-map',
            'station_source':{'kind':'operator_survey','asset_id':'source-backed-test-station',
                              'source_sha256':'3'*64},
            'public_before':ref(7,1,before),'public_at':ref(7,1,0),
            'public_after':ref(7,1,after),'driveway_at':ref(8,2,6),
            'routes':{'front_entrance_turn':[ref(7,1,before),ref(7,1,0),
                                              ref(7,1,after)]},
            'other_route':[ref(7,-1,8),ref(7,-1,6),ref(7,-1,4)]}


class Map:
    name='source-bound-test-map'
    def get_waypoint_xodr(self,road,lane,s):
        if road not in (7,8):return None
        x,y=(0,s) if road==8 else (s,0)
        return S(road_id=road,lane_id=lane,s=s,lane_width=3.0,
                 transform=S(location=S(x=x,y=y)))


class Actor:
    def __init__(self,x,y,yaw):
        self.pose=S(location=S(x=x,y=y),rotation=S(yaw=yaw))
        self.control=None
    def get_transform(self):return self.pose
    def get_velocity(self):return S(x=0.,y=0.)
    def apply_control(self,control):self.control=control


class RunnerTests(unittest.TestCase):
    def config(self,reverse=False):
        return {'law_id':'LVMC-11-12-060','cell_id':'C111706',
                'actor':'motor_vehicle_driver','case_branch':'front_entrance_turn',
                'selected_case_id':'heldout__C111706__LVMC-11-12-060__motor_vehicle_driver__front_entrance_turn',
                'rate_hz':20,'frames':240,'duration_s':12,'required_atoms':[],
                'cameras':[{'name':name} for name in
                           ('overview','approach','reference_corner','driver_reference')],
                'station_survey':survey(reverse),
                'target_speed_mps':4.,'other_speed_mps':2.}

    def test_both_approaches_resolve_distinct_station_and_other_routes(self):
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                config=self.config(reverse)
                self.assertTrue(check_config(config))
                subject,other,original=resolve_survey(Map(),config['station_survey'],
                                                       config['case_branch'])
                self.assertEqual(len(subject),3)
                self.assertEqual(len(other),3)
                self.assertEqual(original['public_before']['xy'][0],8 if reverse else -8)
                self.assertEqual(original['driveway_at']['road_id'],8)

    def test_wrong_map_or_missing_other_route_rejected(self):
        config=self.config()
        config['station_survey']['map_name']='another map'
        with self.assertRaisesRegex(ValueError,'Native map differs'):
            resolve_survey(Map(),config['station_survey'],config['case_branch'])
        config=self.config()
        del config['station_survey']['other_route']
        with self.assertRaisesRegex(ValueError,'other-vehicle connected routes'):
            check_config(config)

    def test_bounded_controller_commands_both_approach_directions(self):
        carla=S(VehicleControl=lambda **values:values)
        east=Actor(-5,0,0);west=Actor(5,0,180)
        steer_toward(east,S(transform=S(location=S(x=-3,y=0))),4.,carla)
        steer_toward(west,S(transform=S(location=S(x=3,y=0))),2.,carla)
        for actor in (east,west):
            self.assertGreater(actor.control['throttle'],0)
            self.assertTrue(-.6<=actor.control['steer']<=.6)

    def test_three_candidate_engineering_knobs(self):
        base=self.config()
        for key,value in (('spawn_height_m',.45),
                          ('waypoint_arrival_m',3.),
                          ('overview_height_delta_m',2.)):
            self.assertTrue(check_config(dict(base,**{key:value})))
        self.assertEqual(plans(2.)[0].location[2]-plans()[0].location[2],2.)
        with self.assertRaisesRegex(ValueError,'overview height'):
            check_config(dict(base,overview_height_delta_m=3.))


if __name__=='__main__':unittest.main()
