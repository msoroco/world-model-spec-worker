import importlib.util,types,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('officer_native_runner',ROOT/'officer_native_runner.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class NativeConstructionTests(unittest.TestCase):
    def test_all_exact_cases_have_distinct_post_direction_controls(self):
        for suffix,(command,responds) in module.CASES.items():
            config={'law_id':'NRS-484B-100','cell_id':'C10365','actor':'motor_vehicle_driver',
                    'selected_case_id':module.PREFIX+suffix,'case':{'case_id':module.PREFIX+suffix},
                    'rate_hz':20,'frames':160,'cameras':[{}]*4,'direction_frame':40}
            self.assertEqual(module.check_config(config),(command,responds))
            self.assertEqual(module.command_for(command,responds,39,40),{'throttle':.16,'brake':0.0})
            following=module.command_for(command,responds,40,40)
            counterpart=module.command_for(command,not responds,40,40)
            self.assertNotEqual(following,counterpart)
    def test_connected_alley_and_sidewalk_required(self):
        class Lane:
            lane_width=2.9;is_junction=False;road_id=7;lane_id=-1
            def next(self,distance):return [self.front]
            def get_right_lane(self):return self.side
        lane=Lane();lane.front=Lane();lane.side=type('Side',(),{'lane_type':'Sidewalk'})()
        world=type('Map',(),{'get_spawn_points':lambda self:[type('Spawn',(),{'location':object()})()],
                              'get_waypoint':lambda self,location:lane})()
        self.assertIs(module.choose_alley_route(world)[0],lane)
        lane.side=None
        with self.assertRaisesRegex(ValueError,'alley lane'):module.choose_alley_route(world)
    def test_visible_arm_control_uses_walker_bone_api(self):
        class Walker:
            def get_bones(self):return type('Bones',(),{'bone_transforms':[('root',None,None,None),('upperarm_r',None,None,None)]})()
            def set_bones(self,value):self.bones=value
            def blend_pose(self,value):self.blend=value
        carla=types.SimpleNamespace(Location=lambda *args:None,Rotation=lambda **kw:kw,
                                   Transform=lambda loc,rot:(loc,rot),WalkerBoneControlIn=lambda data:data)
        walker=Walker();stop=module.pose_direction(carla,walker,'stop')
        self.assertEqual(stop['bone'],'upperarm_r');self.assertEqual(walker.blend,1.0)
        proceed=module.pose_direction(carla,walker,'proceed')
        self.assertNotEqual(stop['relative_pitch_deg'],proceed['relative_pitch_deg'])

if __name__=='__main__':unittest.main()
