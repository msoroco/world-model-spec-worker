import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_comparison_audit as comparison


class NativeComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        self.ids = next(row['case_ids'] for row in plan['comparisons']
                        if row['comparison_id'] == 'right_angle_vs_neither')
        self.attempts = []
        for index, case_id in enumerate(self.ids):
            attempt = self.root / str(index)
            attempt.mkdir()
            exact = ROOT / 'cases' / case_id.removeprefix(ROOT.name + '__')
            for name in ('scene.json', 'config.json'):
                shutil.copyfile(exact / name, attempt / name)
            refs = {fact: {'sha256': 'a' * 64}
                    for fact in comparison.FIXED_SITE_FACTS + ('crosswalk_boundaries_xy_m',)}
            (attempt / 'reviewed-site-audit.json').write_text(json.dumps({
                'case_id': case_id, 'source_refs': refs}) + '\n')
            self.attempts.append(attempt)

    def check(self, site_audit=None, comparison_id='right_angle_vs_neither'):
        def measured(attempt):
            index = [path.resolve() for path in self.attempts].index(pathlib.Path(attempt).resolve())
            return {'case_id': self.ids[index], 'diagnostic_fixture': False,
                    'sources_sha256': {'scene.json': comparison.sha(attempt / 'scene.json')}}

        def pixels(attempt, review, case_id, diagnostic=False):
            return {'case_id': case_id, 'passed': True, 'original_camera_frames': 400,
                    'source_review_sha256': 'b' * 64}

        if site_audit is None:
            site_audit = lambda scene, attempt: json.loads((attempt / 'reviewed-site-audit.json').read_text())
        with patch.object(comparison, 'read_attempt', side_effect=measured), \
             patch.object(comparison, 'audit_pixels', side_effect=pixels), \
             patch.object(comparison, 'audit_reviewed_site', side_effect=site_audit):
            return comparison.audit(comparison_id, *self.attempts,
                                    self.root / 'review-left', self.root / 'review-right',
                                    package=ROOT)

    def test_native_pair_keeps_reviewed_site_fixed(self):
        result = self.check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['status'], 'native_originals_reviewed')

    def test_changed_independent_roadway_source_rejected(self):
        path = self.attempts[1] / 'reviewed-site-audit.json'
        site = json.loads(path.read_text())
        site['source_refs']['roadway_highway_public_use']['sha256'] = 'c' * 64
        path.write_text(json.dumps(site) + '\n')
        with self.assertRaisesRegex(ValueError, 'fixed reviewed site source changed'):
            self.check()

    def test_both_missing_independent_sources_rejected(self):
        for attempt in self.attempts:
            path = attempt / 'reviewed-site-audit.json'
            site = json.loads(path.read_text())
            del site['source_refs']['roadway_highway_public_use']
            path.write_text(json.dumps(site) + '\n')
        with self.assertRaisesRegex(ValueError, 'reviewed site source missing'):
            self.check()

    def test_forged_site_receipt_rejected(self):
        def original(scene, attempt):
            site = json.loads((attempt / 'reviewed-site-audit.json').read_text())
            site['reviewed_packet_sha256'] = 'b' * 64
            return site

        with self.assertRaisesRegex(ValueError, 'receipt differs from original documents'):
            self.check(site_audit=original)

    def test_changed_crosswalk_needs_distinct_reviewed_source(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        self.ids = next(row['case_ids'] for row in plan['comparisons']
                        if row['comparison_id'] == 'outside_vs_crosswalk_exception')
        for attempt, case_id in zip(self.attempts, self.ids):
            exact = ROOT / 'cases' / case_id.removeprefix(ROOT.name + '__')
            for name in ('scene.json', 'config.json'):
                shutil.copyfile(exact / name, attempt / name)
            site = json.loads((attempt / 'reviewed-site-audit.json').read_text())
            site['case_id'] = case_id
            (attempt / 'reviewed-site-audit.json').write_text(json.dumps(site) + '\n')
        with self.assertRaisesRegex(ValueError, 'changed crosswalk needs distinct reviewed source'):
            self.check(comparison_id='outside_vs_crosswalk_exception')


if __name__ == '__main__':
    unittest.main()
