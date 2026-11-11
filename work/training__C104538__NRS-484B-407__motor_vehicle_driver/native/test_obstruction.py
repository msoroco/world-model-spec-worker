import math
import unittest
from cameras import camera_plan
from obstruction import check,placements


class PhysicalProposalTest(unittest.TestCase):
    def test_twelve_barrier_layouts_have_bounded_center_spacing(self):
        result=check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['candidate_layouts'],12)
        self.assertFalse(result['native_actor_spawned'])

    def test_fallback2_halves_segment_spacing(self):
        for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
            primary=placements(suffix,'primary')
            fallback=placements(suffix,'fallback2')
            self.assertGreater(len(fallback),len(primary))
            self.assertLess(fallback[1]['authored_segment_step_m'],
                            primary[1]['authored_segment_step_m'])

    def test_reference_camera_height_changes_only_for_fallback3(self):
        for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
            baseline=camera_plan(suffix,'primary')
            raised=camera_plan(suffix,'fallback3')
            self.assertEqual([v['name'] for v in baseline],
                             [v['name'] for v in raised])
            for a,b in zip(baseline,raised):
                if a['attachment'] in ('reference_left','reference_right'):
                    self.assertEqual(b['native_xyz_m'][2]-a['native_xyz_m'][2],2)
                else:self.assertEqual(a,b)
