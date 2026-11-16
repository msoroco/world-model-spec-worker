import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overtake_geometry import measure

def rectangle(center_x,center_y):
    return [[center_x-.5,center_y-.4],[center_x+.5,center_y-.4],[center_x+.5,center_y+.4],[center_x-.5,center_y+.4]]
def frame(index,other_x,ego_y=0.,speed=4.,other_y=1.5):
    return {'frame':100+index,'time_s':index*.05,'road_forward_xy':[1.,0.],
            'ego':{'id':'ego','speed_mps':speed,'body_corners_xy_m':rectangle(0.,ego_y)},
            'overtaker':{'id':'passing','speed_mps':6.,'body_corners_xy_m':rectangle(other_x,other_y)}}
class OvertakeGeometryTests(unittest.TestCase):
    def test_full_body_completion_is_bracketed_and_speed_before_only(self):
        rows=[frame(0,-2),frame(1,0,ego_y=-.2,speed=4.5),frame(2,2,ego_y=-.2,speed=5.),frame(3,3,ego_y=-.2,speed=7.)]
        value=measure(rows,'ego','passing')
        self.assertEqual(value['completion_interval_s'],[.05,.1])
        self.assertEqual(value['first_complete_frame'],102)
        self.assertEqual(value['max_precompletion_speed_increase_mps'],.5)
        self.assertAlmostEqual(value['max_precompletion_right_shift_m'],.2)
        self.assertEqual(value['passing_side_at_first_frame'],'left')
        self.assertIsNone(value['observation_or_hearing_confirmed'])
    def test_step_increase_is_retained_even_below_initial_speed(self):
        rows=[frame(0,-3,speed=5.),frame(1,-2,speed=3.),frame(2,0,speed=4.),frame(3,2,speed=4.)]
        value=measure(rows,'ego','passing')
        self.assertEqual(value['max_precompletion_speed_increase_mps'],0.)
        self.assertEqual(value['max_precompletion_step_speed_increase_mps'],1.)
        self.assertFalse(value['post_completion_overlap_recurrence'])

    def test_unfinished_pass_and_right_side_remain_unresolved(self):
        value=measure([frame(0,-2,other_y=-1.5),frame(1,-1,other_y=-1.5),frame(2,0,other_y=-1.5)],'ego','passing')
        self.assertIsNone(value['first_complete_frame'])
        self.assertEqual(value['passing_side_at_first_frame'],'right')
    def test_rejects_missing_body_frame_or_changed_actor(self):
        rows=[frame(0,-2),frame(1,0),frame(2,2)]
        rows[1]['overtaker']['body_corners_xy_m']=rows[1]['overtaker']['body_corners_xy_m'][:3]
        with self.assertRaisesRegex(ValueError,'four original overtaker'):measure(rows,'ego','passing')
        rows[1]=frame(1,0);rows[1]['time_s']=.15
        with self.assertRaisesRegex(ValueError,'not 20 Hz'):measure(rows,'ego','passing')
        rows[1]=frame(1,0);rows[1]['overtaker']['id']='other'
        with self.assertRaisesRegex(ValueError,'identity changed'):measure(rows,'ego','passing')
if __name__=='__main__':unittest.main()
