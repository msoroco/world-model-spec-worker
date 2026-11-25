import unittest
import runner

class TestNative(unittest.TestCase):
    def test_exact_three_rider_contract(self):
        self.assertEqual(runner.config_check()['case_id'],runner.CASE)
        self.assertEqual(runner.COUNT,600)
        self.assertEqual(len(runner.CAMERAS),4)

    def test_three_distinct_riders_required(self):
        survey={key:'synthetic-review:'+key for key in (
            'map_name','map_source','public_dedication_source','public_vehicle_access_source',
            'roadway_boundary_source','shoulder_boundary_source','exclusive_use_source',
            'rider_device_source','bicycle_wheel_source','bicycle_diameter_source',
            'bicycle_moped_exclusion_source')}
        survey['exclusive_use_reviewed']=True
        survey['camera_world_transforms']={name:{'xyz_m':[0,0,2],'rotation_deg':[0,0,0]}
                                           for name in runner.CAMERAS}
        survey['riders']=[{'rider_id':i,'device_subtype':'bicycle',
            'device_blueprint':'synthetic-bike','rider_blueprint':'synthetic-rider',
            'spawn_xyz_m':[0,i*1.5,0], 'attach_xyz_m':[0,0,1],
            'target_speed_mps':2,'roadway_occupied':True,
            'shoulder_occupied':False,'exclusive_use_occupied':False}
            for i in (1,2,3)]
        self.assertEqual(len(runner.survey_check(survey)['riders']),3)
        survey['riders'][2]['rider_id']=2
        with self.assertRaisesRegex(ValueError,'three distinct riders'):
            runner.survey_check(survey)

if __name__=='__main__':unittest.main()
