import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner
class RunnerTest(unittest.TestCase):
    def config(self):
        return {'selected_case_id':'heldout__C136529__NRS-484B-623-1__motor_vehicle_driver__slow_with_following_traffic',
                'law_id':'NRS-484B-623-1','cell_id':'C136529','actor':'motor_vehicle_driver',
                'case_branch':'slow_with_following_traffic','rate_hz':20,'frames':160,'duration_s':8,'cameras':[{'name':n} for n in runner.CAMERAS],
                'case':{'recording_description':{'channels':[]}}}
    def test_exact_identity_and_camera_contract(self):
        self.assertTrue(runner.check_config(self.config()))
        bad=dict(self.config(),frames=100)
        with self.assertRaisesRegex(ValueError,'160 original'):runner.check_config(bad)
        bad=dict(self.config(),selected_case_id='other')
        with self.assertRaisesRegex(ValueError,'exact supported'):runner.check_config(bad)
    def test_speed_sign_selection_requires_physical_native_actor(self):
        sign=SimpleNamespace(id=5,type_id='traffic.speed_limit.30',is_alive=True,
            get_transform=lambda:SimpleNamespace(location=SimpleNamespace(x=5,y=0)))
        ego=SimpleNamespace(get_transform=lambda:SimpleNamespace(location=SimpleNamespace(x=0,y=0)))
        world=SimpleNamespace(get_actors=lambda:SimpleNamespace(filter=lambda pattern:[sign]))
        self.assertIs(runner._find_speed_sign(world,ego),sign)
        with self.assertRaisesRegex(ValueError,'No physical 30'):
            runner._find_speed_sign(world,ego,max_distance_m=1)
    def test_obstruction_control_slows_near_physical_actor(self):
        def actor(y):return SimpleNamespace(get_transform=lambda:SimpleNamespace(location=SimpleNamespace(x=0,y=y)))
        ego=actor(0)
        self.assertEqual(runner._obstruction_target(ego,actor(40),3),3)
        self.assertLess(runner._obstruction_target(ego,actor(11),3),3)
    def test_follower_control_responds_to_gap(self):
        def actor(y,speed):
            return SimpleNamespace(get_transform=lambda:SimpleNamespace(location=SimpleNamespace(x=0,y=y)),
                get_velocity=lambda:SimpleNamespace(x=0,y=speed))
        ego=actor(20,3)
        self.assertGreater(runner._follower_target(ego,actor(0,8)),
                           runner._follower_target(ego,actor(11,8)))
if __name__=='__main__':unittest.main()
