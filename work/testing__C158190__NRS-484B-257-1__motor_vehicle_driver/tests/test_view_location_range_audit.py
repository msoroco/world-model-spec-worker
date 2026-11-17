import copy
import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from view_location_range_audit import audit


def sources():
    context = {'view_occluder': {'actor_id': 912,
               'source_kind': 'original_native',
               'blueprint': 'static.prop.streetbarrier',
               'native_location_m': [-4., 12., 0.],
               'body_bounds_m': {'x': [-4.5, -3.5], 'y': [11.5, 12.5], 'z': [0., 2.]}}}
    rows = []
    for i in range(600):
        ego_x = -60. + 52. * i / 599
        fraction = (-4. - ego_x) / (1.8 - ego_x)
        crossing_y = 1.8 + fraction * 18.2
        blocked = 0 <= fraction <= 1 and 11.5 <= crossing_y <= 12.5
        rows.append({'frame': 100 + i, 'method': 'native_collision_ray_to_authored_through_lane_point',
                     'ego_distance_to_junction_m': 52. - 52. * i / 599,
                     'observer_m': [ego_x, 1.8, 1.75],
                     'target_m': [1.8, 20., 1.5], 'target_road_id': 158194,
                     'target_lane_id': -1, 'blockers':
                     [{'label': 'native_hit', 'location_m': [-4., crossing_y, 1.75 - .25*fraction]}] if blocked else [],
                     'clear': not blocked})
    return rows, context


class ViewRangeAuditTests(unittest.TestCase):
    def test_draft_native_controller_accepts_exact_view_cases(self):
        root = Path(__file__).resolve().parents[1]
        for center in (12, 15, 18):
            with self.subTest(center=center):
                construction = json.loads((root / f'cases/view_location_y{center}/construction.json').read_text())
                source = next(item['content'] for item in construction['files']
                              if item['path'] == 'yield_controller.py')
                name = f'c158190_view_stage_{center}'
                module = types.ModuleType(name)
                sys.modules[name] = module
                try:
                    exec(compile(source, name, 'exec'), module.__dict__)
                    case = root.name + f'__yield_nearest_view_occluder_y{center}'
                    stage = module.Stage(case)
                    self.assertEqual(stage.target(30., within_intersection=False,
                                                  through_vehicle_clear=False), 6.)
                    self.assertEqual(stage.target(10., within_intersection=False,
                                                  through_vehicle_clear=False), 2.)
                finally:
                    del sys.modules[name]

    def test_original_continuous_range_and_obstruction_transition(self):
        rows, context = sources()
        result = audit(rows, context)
        self.assertEqual(len(result['observed_transition_frames']), 2)
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_rejects_fixture_and_short_history(self):
        rows, context = sources()
        context['view_occluder']['source_kind'] = 'synthetic_diagnostic'
        with self.assertRaisesRegex(ValueError, 'Original Native road context'):
            audit(rows, context)
        context['view_occluder'].pop('source_kind')
        with self.assertRaisesRegex(ValueError, 'Original Native road context'):
            audit(rows, context)
        _, context = sources()
        context['view_occluder']['actor_id'] = None
        with self.assertRaisesRegex(ValueError, 'Original obstruction identity'):
            audit(rows, context)
        rows, context = sources()
        with self.assertRaisesRegex(ValueError, 'too short'):
            audit(rows[:2], context)

    def test_rejects_missing_prop_hit_and_frame_gap(self):
        rows, context = sources()
        changed = copy.deepcopy(rows)
        for row in changed:
            if row['blockers']:
                row['blockers'][0]['location_m'][1] += 2.
        with self.assertRaisesRegex(ValueError, 'off sight ray'):
            audit(changed, context)
        changed = copy.deepcopy(rows)
        changed[300]['frame'] += 2
        with self.assertRaisesRegex(ValueError, 'not contiguous'):
            audit(changed, context)

    def test_rejects_changed_target_and_reversed_motion(self):
        rows, context = sources()
        changed = copy.deepcopy(rows)
        changed[5]['target_m'][1] = 0.
        with self.assertRaisesRegex(ValueError, 'target changed'):
            audit(changed, context)
        changed = copy.deepcopy(rows)
        changed[5]['ego_distance_to_junction_m'] += 1.
        with self.assertRaisesRegex(ValueError, 'distance reversed'):
            audit(changed, context)


if __name__ == '__main__':
    unittest.main()
