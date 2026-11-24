import copy
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import runner

class Lane:
    def __init__(self,road_id,lane_id):
        self.road_id,self.lane_id=road_id,lane_id

class TestTwoPhaseConstruction(unittest.TestCase):
    def test_exact_config_and_road(self):
        if (Path(runner.__file__).resolve().parent/'config.json').exists():
            self.assertEqual(runner.config()['frames'],600)
        road=ET.fromstring(runner.road_xml()).find('road')
        self.assertEqual(road.attrib['id'],'405647')
        self.assertEqual({lane.attrib['id'] for lane in road.findall('lanes/laneSection/*/lane')},{'-1','0','1'})
    def test_survey_rejects_unreviewed_authorization(self):
        survey={'map_name':'C405647-two-phase-emergency','map_source':'review',
                'road_geometry_source':'authored:runner.road_xml','ego_blueprint':'vehicle.tesla.model3',
                'emergency_blueprint':'vehicle.dodge.charger_police',
                'ego_spawn_xyz_m':[-75,-1.75,0.5],'emergency_spawn_xyz_m':[-15,1.75,0.5],
                'camera_world_transforms':{n:{'xyz_m':[0,0,1],'rotation_deg':[0,0,0]} for n in runner.CAMERAS},
                'emergency_authorization_source':'review','qualifying_flash_equipment_source':'review',
                'officer_direction_review_source':'review','emergency_vehicle_authorized':False,
                'qualifying_flash_equipment_reviewed':True,'officer_directed_otherwise':False}
        with self.assertRaisesRegex(ValueError,'authorization'):runner.survey_check(survey)
        survey['emergency_vehicle_authorized']=True
        self.assertIs(runner.survey_check(survey),survey)
        broken=copy.deepcopy(survey);broken['emergency_spawn_xyz_m'][1]=-1.75
        with self.assertRaisesRegex(ValueError,'Two-direction'):runner.survey_check(broken)

    def test_native_lane_readback_is_opposing_and_same_road(self):
        self.assertEqual(runner.validate_native_lanes(Lane(405647,-1),Lane(405647,1)),
                         {'road_id':405647,'ego_lane_id':-1,'emergency_lane_id':1})
        for ego,emergency in ((None,Lane(405647,1)),
                              (Lane(405647,-1),None),
                              (Lane(8,-1),Lane(405647,1)),
                              (Lane(405647,-1),Lane(405647,-1))):
            with self.assertRaises(ValueError):runner.validate_native_lanes(ego,emergency)

    def test_subsection_one_response_requests_right_edge_stop_until_passed(self):
        compliant={'case_suffix':'controlled_1','requested_initial_subject_speed_mps':3,
                   'requested_subsequent_subject_speed_mps':0,
                   'requested_right_edge_center_y_m':-2.5}
        continuing={**compliant,'case_suffix':'controlled_2',
                    'requested_subsequent_subject_speed_mps':3}
        self.assertEqual(runner.subject_response(99,compliant,-60,-1.75,-15),(3,0.0,'initial_approach'))
        self.assertEqual(runner.subject_response(110,compliant,-59,-2.125,-14),(1.0,-0.75,'move_to_right_edge'))
        self.assertAlmostEqual(runner.subject_response(100,compliant,-59,-2.1,-14)[1],-.4)
        self.assertEqual(runner.subject_response(220,compliant,-59,-2.5,-27),(0.0,0.0,'stopped_until_passed'))
        self.assertEqual(runner.subject_response(580,compliant,-59,-2.5,-65),(1.0,0.0,'resumed_after_pass'))
        self.assertEqual(runner.subject_response(220,continuing,-20,-1.75,-27),(3,0.0,'continued_travel'))

if __name__=='__main__':unittest.main()
