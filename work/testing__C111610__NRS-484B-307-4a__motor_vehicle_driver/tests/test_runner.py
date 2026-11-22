import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import load_scene,sole_turn_arrow,lawful_occupants,control,turn_route,route_steer

def body(x,y):return [[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]]
def signal(frame):return {'source_verified':True,'source_ref':'Native head 7',
    'head_id':7,'observed_frame':frame,
    'illuminated_indications':[{'color':'green','shape':'arrow','direction':'left'}]}
def pedestrian(y):return {'id':'person-1','role':'pedestrian','source_ref':'Native person',
    'lawfully_present':True,'lawful_presence_source':'Native crosswalk phase',
    'body_vertices_m':body(0,y)}


class LeftArrowRunnerTests(unittest.TestCase):
    def test_turn_route_crosses_adjacent_crosswalk(self):
        scene=load_scene();route=turn_route(scene)
        self.assertEqual(route[0],[-20,-1.75])
        self.assertEqual(route[-1],[0,20])
        self.assertLess(route[2][1],scene['adjacent_crosswalk_bounds_m'][1])
        self.assertGreater(route[-1][1],scene['adjacent_crosswalk_bounds_m'][3])

    def test_requires_sole_facing_original_left_arrow(self):
        scene=load_scene();self.assertTrue(sole_turn_arrow(signal(100),scene,100))
        for mutation in ({'head_id':8},{'observed_frame':99},{'source_verified':False},
                         {'illuminated_indications':[{'color':'green','shape':'circle','direction':'none'}]},
                         {'illuminated_indications':signal(100)['illuminated_indications']+
                             [{'color':'green','shape':'circle','direction':'none'}]}):
            changed=dict(signal(100),**mutation)
            with self.assertRaises(ValueError):sole_turn_arrow(changed,scene,100)

    def test_hold_for_lawful_adjacent_pedestrian_or_traffic(self):
        scene=load_scene()
        self.assertEqual(lawful_occupants([pedestrian(5)],scene),['person-1'])
        self.assertEqual(lawful_occupants([pedestrian(12)],scene),[])
        hold=control(scene,signal(100),100,body(-7,-1.75),[pedestrian(5)],[])
        self.assertEqual((hold['throttle'],hold['brake']), (0,1))
        self.assertTrue(hold['hold_target_met'])
        proceeded=control(scene,signal(100),100,body(-7,-1.75),[],[],0)
        self.assertEqual((proceeded['throttle'],proceeded['brake']),(.2,0))
        traffic=[{'id':'car-2','source_ref':'Native vehicle','lawful_presence_source':'Native phase',
                  'lawfully_using_intersection':True}]
        self.assertEqual(control(scene,signal(100),100,body(-7,-1.75),[],traffic)['brake'],1)
        self.assertFalse(control(scene,signal(100),100,body(-3,-1.75),[pedestrian(5)],[])['hold_target_met'])
        missing=pedestrian(5);missing.pop('lawful_presence_source')
        with self.assertRaisesRegex(ValueError,'lawful-presence source'):
            control(scene,signal(100),100,body(-7,-1.75),[missing],[])

    def test_route_control_requires_heading_and_turns_left(self):
        scene=load_scene()
        with self.assertRaisesRegex(ValueError,'heading'):
            control(scene,signal(100),100,body(-7,-1.75),[],[])
        self.assertAlmostEqual(route_steer(scene,[-10,-1.75],0),0)
        self.assertGreater(route_steer(scene,[-4,-1.75],0),0)
        self.assertAlmostEqual(route_steer(scene,[0,2],90),0)


if __name__=='__main__':unittest.main()
