import importlib.util
import unittest
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/'pedestrian_control.py'
spec=importlib.util.spec_from_file_location('pedestrian_control_c109171',MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class FakeActor:
    def __init__(self,x,y): self.x=x;self.y=y;self.control=None
    def get_location(self): return self
    def apply_control(self,c): self.control=c

class ControlTest(unittest.TestCase):
    site={'pedestrian_route_xy':[[-2,1],[-1,1],[1,1],[3,1]]}
    @staticmethod
    def control(**kw): return kw
    @staticmethod
    def vector(x,y,z): return (x,y,z)
    def test_wait_cases_hold_even_with_walk(self):
        for suffix in ('arrow_wait','arrow_walk_wait'):
            actor=FakeActor(-2,1)
            mod.apply_case(actor,suffix,self.site,self.control,self.vector)
            self.assertEqual(actor.control['speed'],0)
    def test_entry_cases_move_toward_highway(self):
        for suffix in ('arrow_early_entry','arrow_walk_entry'):
            actor=FakeActor(-2,1)
            mod.apply_case(actor,suffix,self.site,self.control,self.vector)
            self.assertEqual(actor.control['direction'],(1.0,0.0,0))
            self.assertEqual(actor.control['speed'],1.2)
    def test_unknown_case_and_bad_speed_rejected(self):
        with self.assertRaises(ValueError):mod.target_control('other',self.site,(-2,1),self.control,self.vector)
        with self.assertRaises(ValueError):mod.target_control('arrow_early_entry',self.site,(-2,1),self.control,self.vector,3)
    def test_follower_advances_without_backtracking_and_stops(self):
        follower=mod.RouteFollower('arrow_walk_entry',self.site)
        self.assertEqual(follower.control((-2,1),self.control,self.vector)['direction'],(1.0,0.0,0))
        self.assertEqual(follower.control((-1,1),self.control,self.vector)['direction'],(1.0,0.0,0))
        self.assertEqual(follower.next_index,2)
        self.assertEqual(follower.control((1,1),self.control,self.vector)['direction'],(1.0,0.0,0))
        self.assertEqual(follower.next_index,3)
        self.assertEqual(follower.control((3,1),self.control,self.vector)['speed'],0)
        self.assertEqual(follower.control((3.2,1),self.control,self.vector)['speed'],0)
    def test_follower_rejects_bad_route_and_position(self):
        with self.assertRaisesRegex(ValueError,'nonfinite coordinate'):
            mod.RouteFollower('arrow_early_entry',{'pedestrian_route_xy':[[0,0],[float('nan'),1],[2,1]]})
        follower=mod.RouteFollower('arrow_early_entry',self.site)
        with self.assertRaisesRegex(ValueError,'nonfinite walker position'):
            follower.control((float('inf'),1),self.control,self.vector)
    def test_four_cited_sweep_controller_delays_are_distinct(self):
        for index in range(4):
            suffix='permission_applicability-'+str(index).zfill(4)
            follower=mod.RouteFollower(suffix,self.site)
            delay=mod.SWEEP_ENTRY_DELAY_TICKS[suffix]
            for _ in range(delay):
                self.assertEqual(follower.control((-2,1),self.control,self.vector)['speed'],0)
            self.assertEqual(follower.control((-2,1),self.control,self.vector)['speed'],1.2)

if __name__=='__main__':unittest.main()
