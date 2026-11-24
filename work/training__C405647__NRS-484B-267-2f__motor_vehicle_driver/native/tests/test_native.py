import copy
import unittest
import xml.etree.ElementTree as ET
import runner

class TestTwoPhaseConstruction(unittest.TestCase):
    def test_exact_config_and_road(self):
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

if __name__=='__main__':unittest.main()
