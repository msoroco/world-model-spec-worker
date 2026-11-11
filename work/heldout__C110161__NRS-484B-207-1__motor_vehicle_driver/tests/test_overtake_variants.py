import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from overtake_variants import left_target_xy, return_target
from variant_runner import check_config
from test_overtake_route import lanes


def corners(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class OvertakeVariantTests(unittest.TestCase):
    def test_signed_return_is_distinct_and_requires_abreast(self):
        world_map, _, _ = lanes()
        route = __import__('overtake_route').select_overtake_route(world_map)
        kwargs = dict(passed_abreast=True, lookahead=3)
        early = return_target(route, [10, 3.5], 8, 9,
                              requested_return_clearance_m=-1, **kwargs)
        late = return_target(route, [10, 3.5], 8, 9,
                             requested_return_clearance_m=3, **kwargs)
        unobserved = return_target(route, [10, 3.5], 8, 9,
                                   requested_return_clearance_m=-1,
                                   passed_abreast=False)
        self.assertEqual(early['phase'], 'return_right')
        self.assertEqual(late['phase'], 'pass_left')
        self.assertEqual(unobserved['phase'], 'pass_left')
        self.assertEqual(early['measured_body_clearance_m'], -1)

    def test_lateral_target_uses_original_bodies_in_both_directions(self):
        for direction in (1, -1):
            waypoint = NS(transform=NS(location=NS(x=0, y=3.5 * direction)))
            row = {'road_tangent_xy': [direction, 0],
                   'other_corners': corners(5, 9, 0, 2 * direction),
                   'ego_corners': corners(5, 9, 3 * direction, 5 * direction)}
            narrow = left_target_xy(waypoint, row, .5)
            wide = left_target_xy(waypoint, row, 2)
            self.assertAlmostEqual((wide[1] - narrow[1]) * direction, 1.5)
            self.assertAlmostEqual(narrow[1] * direction, 3.5)
            row['ego_corners'][0][0] = float('nan')
            with self.assertRaisesRegex(ValueError, 'Nonfinite'):
                left_target_xy(waypoint, row, .5)

    def test_exact_variant_configuration(self):
        base = json.loads((HERE / 'config.json').read_text())
        for suffix, settings in (('left_pass_narrow', (.5, 3)),
                                 ('return_before_clear', (1.25, -1)),
                                 ('return_after_clear', (1.25, 3))):
            case = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__' + suffix
            config = {**base, 'selected_case_id': case,
                      'supported_case_ids': [case],
                      'target_left_gap_m': settings[0],
                      'requested_return_clearance_m': settings[1]}
            config['case'] = {**base['case'], 'case_id': case}
            check_config(config)
            with self.assertRaisesRegex(ValueError, 'control settings differ'):
                check_config({**config, 'requested_return_clearance_m': 0})


if __name__ == '__main__':
    unittest.main()
