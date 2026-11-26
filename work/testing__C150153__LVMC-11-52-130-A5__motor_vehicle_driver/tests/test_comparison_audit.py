"""Synthetic sealed attempts test frozen-pair comparison protocol only."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import compare
from parking import CASES
from test_independent_delivery_audit import DeliveryAuditTests, sha


class ComparisonAuditTests(unittest.TestCase):
    def pair(self, root, left_case='west_inside', right_case='west_at'):
        root = Path(root)
        left_root, right_root = root / 'left', root / 'right'
        left_root.mkdir()
        right_root.mkdir()
        left, packet, sources, _ = DeliveryAuditTests().fixture(left_root, left_case)
        right, other_packet, other_sources, _ = DeliveryAuditTests().fixture(right_root, right_case)
        self.assertEqual(sha(packet), sha(other_packet))
        return left, right, packet, sources

    def test_west_boundary_comparison_and_fixed_weather_rejection(self):
        scratch = Path('.runtime-work/c150153-comparison-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            left, right, packet, sources = self.pair(temp)
            proof = compare('west_below_at', left, right, packet, sources,
                            diagnostic_fixture=True, decoder=lambda path, name: 900)
            self.assertEqual(proof['observed_difference_key'], 'min_side_gap_m')
            self.assertFalse(proof['physical_acceptance_claimed'])
            with self.assertRaisesRegex(ValueError, 'exact pair differs'):
                compare('west_at_above', left, right, packet, sources,
                        diagnostic_fixture=True, decoder=lambda path, name: 900)
            path = right / 'comparison-context.json'
            context = json.loads(path.read_text())
            context['weather_sha256'] = 'changed-weather-source'
            path.write_text(json.dumps(context) + '\n')
            seal_path = right / 'capture-seal.json'
            seal = json.loads(seal_path.read_text())
            seal['sources']['comparison-context.json'] = sha(path)
            seal_path.write_text(json.dumps(seal) + '\n')
            with self.assertRaisesRegex(ValueError, 'fixed condition changed: weather_sha256'):
                compare('west_below_at', left, right, packet, sources,
                        diagnostic_fixture=True, decoder=lambda path, name: 900)

    def test_missing_original_context_rejected(self):
        scratch = Path('.runtime-work/c150153-comparison-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            left, right, packet, sources = self.pair(temp)
            (right / 'comparison-context.json').unlink()
            with self.assertRaisesRegex(ValueError, 'sealed original source missing or changed'):
                compare('west_below_at', left, right, packet, sources,
                        diagnostic_fixture=True, decoder=lambda path, name: 900)

    def test_all_ten_frozen_pairs_have_source_bound_comparison_path(self):
        scratch = Path('.runtime-work/c150153-comparison-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        plan = json.loads((HERE / 'case-plan.json').read_text())
        self.assertEqual(len(plan['comparisons']), 10)
        for spec in plan['comparisons']:
            names = [case_id.removeprefix(HERE.name + '__') for case_id in spec['case_ids']]
            self.assertTrue(all(name in {case.id for case in CASES} for name in names))
            with self.subTest(comparison=spec['comparison_id']), TemporaryDirectory(dir=scratch) as temp:
                left, right, packet, sources = self.pair(temp, *names)
                proof = compare(spec['comparison_id'], left, right, packet, sources,
                                diagnostic_fixture=True, decoder=lambda path, name: 900)
                self.assertEqual(proof['case_ids'], spec['case_ids'])


if __name__ == '__main__':
    unittest.main()
