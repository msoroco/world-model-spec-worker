import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stopping_reference', ROOT / 'stopping_reference.py')
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def geometry(line, walk, view):
    return {
        'ego_intersection_boundary_x_m': -8.0,
        'stop_line': {'present': line, 'x_m': -15.0, 'source': 'authored-site#stop-line'},
        'near_crosswalk': {'present': walk, 'x_m': -13.0, 'source': 'authored-site#crosswalk'},
        'nearest_view': {'present': view, 'x_m': -11.0, 'source': 'authored-site#view-line'},
    }


class ReferenceTests(unittest.TestCase):
    def test_three_authored_site_variants(self):
        cases = (
            ('line-reference-site.xodr', 'stop_line', -15.0),
            ('crosswalk-reference-site.xodr', 'near_crosswalk', -14.0),
            ('nearest-view-reference-site.xodr', 'nearest_view', -11.0),
        )
        for file, kind, expected_x in cases:
            with self.subTest(file=file):
                selected = module.from_authored_site(ROOT / file)
                self.assertEqual(selected['kind'], kind)
                self.assertEqual(selected['x_m'], expected_x)
                self.assertEqual(selected['intersection_boundary_x_m'], -8.0)
                self.assertIn(file, selected['source'])

    def test_reference_hierarchy_and_missing_source(self):
        self.assertEqual(module.select_reference(geometry(True, True, True))['kind'], 'stop_line')
        self.assertEqual(module.select_reference(geometry(False, True, True))['kind'], 'near_crosswalk')
        picked = module.select_reference(geometry(False, False, True))
        self.assertEqual(picked['kind'], 'nearest_view')
        self.assertTrue(picked['legal_visibility_review_pending'])
        with self.assertRaisesRegex(ValueError, 'No sourced stopping reference'):
            module.select_reference(geometry(False, False, False))
        changed = geometry(True, False, False)
        changed['stop_line']['source'] = ''
        with self.assertRaisesRegex(ValueError, 'Unsourced stop_line'):
            module.select_reference(changed)
        changed = geometry(True, False, False)
        changed['stop_line']['x_m'] = -7.0
        with self.assertRaisesRegex(ValueError, 'within intersection'):
            module.select_reference(changed)

    def test_approach_brake_hold_and_overshoot(self):
        reference = module.select_reference(geometry(True, False, False))
        state = module.ApproachState()
        first = module.control_step(state, front_x_m=-35.0, speed_mps=4.0,
                                    reference=reference, hold_ticks=2)
        self.assertEqual(first['phase'], 'approach')
        brake = module.control_step(state, front_x_m=-18.0, speed_mps=4.0,
                                    reference=reference, hold_ticks=2)
        self.assertEqual(brake['phase'], 'braking')
        self.assertEqual(brake['brake'], 1.0)
        hold = module.control_step(state, front_x_m=-15.5, speed_mps=0.0,
                                   reference=reference, hold_ticks=2)
        self.assertEqual(hold['phase'], 'holding')
        release = module.control_step(state, front_x_m=-15.5, speed_mps=0.0,
                                      reference=reference, hold_ticks=2)
        self.assertEqual(release['phase'], 'proceed')
        self.assertTrue(release['engineering_hold_reached'])
        overshot = module.control_step(module.ApproachState(), front_x_m=-14.0,
                                       speed_mps=1.0, reference=reference, hold_ticks=2)
        self.assertEqual(overshot['phase'], 'overshot')
        self.assertEqual(overshot['brake'], 1.0)
        with self.assertRaisesRegex(ValueError, 'Negative ego speed'):
            module.control_step(module.ApproachState(), front_x_m=-20.0,
                                speed_mps=-1.0, reference=reference, hold_ticks=2)


if __name__ == '__main__':
    unittest.main()
