"""Exercise the authored 3 s/5 s controller branches, not just bundle fields."""
import json
import unittest
from pathlib import Path

from hazard_sweep_policy import HazardSweepPolicy

ROOT = Path(__file__).resolve().parent


class HazardReleaseDrafts(unittest.TestCase):
    def config(self, suffix, label='primary'):
        filename = 'construction.json' if label == 'primary' else label + '-construction.json'
        bundle = json.loads((ROOT / 'cases' / suffix / filename).read_text())
        return json.loads(next(row['content'] for row in bundle['files']
                               if row['path'] == 'config.json'))

    def action(self, release, *, distance=16.0, cleared=False):
        policy = HazardSweepPolicy(release_ttc_s=release, approach_speed_mps=5.0)
        return policy.step(distance_to_hold_m=0.0, ego_speed_mps=0.0,
                           oncoming_distance_to_conflict_m=distance,
                           oncoming_closing_speed_mps=4.0,
                           oncoming_in_intersection=False,
                           oncoming_cleared=cleared, turn_complete=False)

    def test_distinct_release_actions_at_same_four_second_source(self):
        short = self.config('approaching_release_3s')['controller_release_ttc_s']
        long = self.config('approaching_release_5s')['controller_release_ttc_s']
        self.assertEqual(self.action(short)['state'], 'turn')
        self.assertEqual(self.action(long)['state'], 'yield')

    def test_seen_hazard_requires_source_clearance_for_both_settings(self):
        for suffix in ('approaching_release_3s', 'approaching_release_5s'):
            release = self.config(suffix)['controller_release_ttc_s']
            policy = HazardSweepPolicy(release_ttc_s=release, approach_speed_mps=5.0)
            common = dict(distance_to_hold_m=0.0, ego_speed_mps=0.0,
                          oncoming_closing_speed_mps=4.0,
                          oncoming_in_intersection=False, turn_complete=False)
            self.assertEqual(policy.step(oncoming_distance_to_conflict_m=4.0,
                                         oncoming_cleared=False, **common)['state'], 'yield')
            self.assertEqual(policy.step(oncoming_distance_to_conflict_m=80.0,
                                         oncoming_cleared=False, **common)['state'], 'yield')
            self.assertEqual(policy.step(oncoming_distance_to_conflict_m=80.0,
                                         oncoming_cleared=True, **common)['state'], 'turn')

    def test_fallbacks_change_one_distinct_physical_control(self):
        for suffix in ('approaching_release_3s', 'approaching_release_5s'):
            baseline = self.config(suffix)
            expected = ('controller_release_ttc_s', 'approach_speed_mps',
                        'reciprocal_approach_speed_mps')
            for label, knob in zip(('fallback1', 'fallback2', 'fallback3'), expected):
                changed = {key for key in expected
                           if self.config(suffix, label)[key] != baseline[key]}
                self.assertEqual(changed, {knob})


if __name__ == '__main__':
    unittest.main()
