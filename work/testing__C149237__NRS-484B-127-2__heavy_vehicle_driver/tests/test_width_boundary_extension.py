"""CPU checks for the three width cases planned after the eight-case bundle."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from width_boundary_extension import WIDTH_M, spawn_width_control_pair
from test_width_construction import CYBER, HGV, World, transform


class WidthBoundaryExtensionTests(unittest.TestCase):
    def test_remaining_width_boundary_roles_select_measured_bodies(self):
        for case, role, width in (
            ('ego_width_above_80in', 'ego', 2.1),
            ('lead_width_at_80in', 'lead', WIDTH_M),
            ('lead_width_above_80in', 'lead', 2.1),
        ):
            with self.subTest(case=case):
                world = World({HGV: 2.2, CYBER: width})
                with spawn_width_control_pair(world, case, HGV, [CYBER], transform) as pair:
                    self.assertEqual(pair['varied_role'], role)
                    self.assertAlmostEqual(pair['realized_widths_m'][role], width)
                    self.assertAlmostEqual(pair['initial_body_gap_m'], 152.4)
                self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_above_width_requires_margin_beyond_boundary(self):
        world = World({HGV: 2.2, CYBER: WIDTH_M + .002})
        with self.assertRaisesRegex(ValueError, 'No pinned truck blueprint'):
            with spawn_width_control_pair(world, 'lead_width_above_80in', HGV, [CYBER], transform):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))
