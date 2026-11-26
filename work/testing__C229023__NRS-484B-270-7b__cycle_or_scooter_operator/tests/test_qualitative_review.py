"""Synthetic source binding checks for both qualitative judgment phrases."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from qualitative_review import review, compare  # noqa: E402


class QualitativeReviewTest(unittest.TestCase):
    def make_attempt(self, root, case_id):
        root.mkdir()
        contract = json.loads((HERE / 'qualitative-review-contract.json').read_text())
        files = {}
        for name in contract['required_sources']:
            path = root / name
            path.write_text(json.dumps({'selected_case_id': case_id}) + '\n' if name == 'config.json' else 'synthetic diagnostic source: ' + name + '\n')
            files[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        (root / 'original-sources.json').write_text(json.dumps({
            'source_kind': 'synthetic_fixture', 'frame_count': 900,
            'case_id': case_id, 'files': files}, indent=2) + '\n')
        observations = {}
        for spec in contract['sweeps']:
            observations[spec['sweep_id']] = {
                'status': 'observed', 'reviewer': 'diagnostic synthetic reviewer',
                'reason': 'source interval and required channel names checked',
                'interval_frames': [100, 500],
                'source_refs': spec['source_refs'], 'legal_verdict': None}
        declaration = root / 'declaration.json'
        declaration.write_text(json.dumps({'case_id': case_id,
                                            'observations': observations,
                                            'legal_verdict': None}, indent=2) + '\n')
        return declaration

    def test_both_phrases_positive_and_no_legal_verdict(self):
        case = 'testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator__bicycle_wider_pass'
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
            root = Path(temp) / 'attempt'
            declaration = self.make_attempt(root, case)
            result = review(HERE / 'qualitative-review-contract.json', root,
                            declaration, diagnostic=True)
            self.assertEqual(set(result['observations']), {'c229023-0', 'c229023-1'})
            self.assertIsNone(result['legal_verdict'])
            with self.assertRaisesRegex(ValueError, 'reviewed original source kind missing'):
                review(HERE / 'qualitative-review-contract.json', root, declaration)

    def test_negative_legal_claim_and_missing_source(self):
        case = 'testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator__bicycle_wider_pass'
        for sweep_id, missing_name in [('c229023-0', 'approach.mkv'),
                                       ('c229023-1', 'reference_corner.mkv')]:
            with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
                root = Path(temp) / 'attempt'
                declaration = self.make_attempt(root, case)
                data = json.loads(declaration.read_text())
                data['observations'][sweep_id]['legal_verdict'] = 'safe'
                declaration.write_text(json.dumps(data) + '\n')
                with self.assertRaisesRegex(ValueError, 'cannot declare a legal verdict'):
                    review(HERE / 'qualitative-review-contract.json', root,
                           declaration, diagnostic=True)
                data['observations'][sweep_id]['legal_verdict'] = None
                data['observations'][sweep_id]['status'] = 'not_observed'
                declaration.write_text(json.dumps(data) + '\n')
                negative = review(HERE / 'qualitative-review-contract.json', root,
                                  declaration, diagnostic=True)
                self.assertEqual(negative['observations'][sweep_id]['status'],
                                 'not_observed')
                (root / missing_name).unlink()
                with self.assertRaisesRegex(ValueError, 'missing or changed original source'):
                    review(HERE / 'qualitative-review-contract.json', root,
                           declaration, diagnostic=True)

    def test_comparison_binds_declared_difference_and_sources(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        for comparison in (plan['comparisons'][0], plan['comparisons'][-1]):
            pair = comparison['case_ids']
            with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
                root = Path(temp)
                reports = []
                for i, case in enumerate(pair):
                    attempt = root / ('attempt-' + str(i))
                    declaration = self.make_attempt(attempt, case)
                    result = review(HERE / 'qualitative-review-contract.json',
                                    attempt, declaration, diagnostic=True)
                    report = root / ('report-' + str(i) + '.json')
                    report.write_text(json.dumps(result) + '\n')
                    reports.append(report)
                observed = compare(HERE / 'case-plan.json', reports[0], reports[1],
                                   comparison['comparison_id'])
                self.assertEqual(observed['declared_differences'],
                                 comparison['deliberate_differences'])
                self.assertEqual(set(observed['observed_statuses']),
                                 {'c229023-0', 'c229023-1'})
                with self.assertRaisesRegex(ValueError, 'comparison cases differ'):
                    compare(HERE / 'case-plan.json', reports[1], reports[0],
                            comparison['comparison_id'])

    def test_exact_case_cli_path(self):
        case = 'testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator__endangerment_offset_low'
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temp:
            root = Path(temp) / 'attempt'
            declaration = self.make_attempt(root, case)
            base = [sys.executable, str(HERE / 'qualitative_review.py'),
                    '--contract', str(HERE / 'qualitative-review-contract.json'),
                    '--attempt', str(root), '--declaration', str(declaration),
                    '--diagnostic']
            passed = subprocess.run(base + ['--case-id', case,
                                            '--output', str(Path(temp) / 'review.json')],
                                    capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            rejected = subprocess.run(base + ['--case-id', case + '-wrong',
                                              '--output', str(Path(temp) / 'wrong.json')],
                                      capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('review selected case differs', rejected.stderr)


if __name__ == '__main__':
    unittest.main()
