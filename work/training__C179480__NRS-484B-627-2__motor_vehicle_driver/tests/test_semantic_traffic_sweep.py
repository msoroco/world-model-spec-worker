"""The planned traffic sweep has exactly the source-probed physical grid."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'runtime' / 'pipeline'))

from build_semantic_cases import assignments  # noqa: E402
from scenario_pipeline.batch_pipeline.sweeps import grid  # noqa: E402


class TrafficSweepContract(unittest.TestCase):
    def test_grid_and_nonaxis_isolation(self):
        read = lambda name: json.loads((HERE / 'proposals' / name).read_text())
        canonical = read('canonical-cases.json')
        binding = read('bindings.json')
        spec = next(s for s in canonical['sweep_specs'] if s['sweep_id'] == 'c179480-traffic-effect-gap')
        probe = json.loads((HERE / 'traffic-effect-sweep-probe.json').read_text())
        self.assertEqual(spec['status'], 'complete')
        self.assertEqual([p['following_gap_m'] for p in grid(spec)], [7.0, 12.0, 9.5])
        self.assertEqual(sorted(r['brake_gap_setting_m'] for r in probe['probe_rows']), [7.0, 9.5, 12.0])
        members = [c for c in canonical['cases'] if c.get('sweep_id') == spec['sweep_id']]
        self.assertEqual([c['case_id'] for c in members], spec['selection_order'])
        self.assertEqual(len(members), 3)
        held = assignments('reference', binding)
        for case, point in zip(members, grid(spec)):
            self.assertEqual(case['sweep_point'], point)
            self.assertEqual(case['variable_assignments']['following_gap_m']['value'], point['following_gap_m'])
            for key in set(held) - {'following_gap_m'}:
                self.assertEqual(case['variable_assignments'][key], held[key])
            self.assertEqual(case['unresolved_judgment_calls'], sorted(case['unresolved_judgment_calls']))
            self.assertIn('following_gap_m', {channel['name'] for channel in case['recording_description']['channels']})

    def test_source_receipt_must_not_claim_native_observation(self):
        receipt = json.loads((HERE / 'traffic-effect-sweep-probe.json').read_text())
        self.assertFalse(receipt['original_native_observed'])
        self.assertFalse(receipt['physical_or_legal_acceptance_claimed'])
        self.assertTrue(all(row['legal_movement_judgment'] == 'independent_original_source_review_required'
                            for row in receipt['probe_rows']))


if __name__ == '__main__':
    unittest.main()
