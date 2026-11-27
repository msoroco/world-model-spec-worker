"""Source-gated four-case construction input tests, with fake Native library."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from test_electric_asset import Library
from electric_case_plan import build


class BothLibrary:
    def __init__(self, ids):
        self.ids = set(ids)

    def filter(self, blueprint_id):
        return Library(blueprint_id).filter(blueprint_id) if blueprint_id in self.ids else []


class ElectricCasePlanTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[4] / '.runtime-work' / 'c230207-electric-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reviews = {}
        for kind, blueprint_id in (('electric_bicycle', 'vehicle.reviewed.ebike'),
                                   ('electric_scooter', 'vehicle.reviewed.escooter')):
            source = self.root / (kind + '.txt')
            source.write_text('Synthetic test review only; no real asset.\n')
            self.reviews[kind] = {
                'machine_class': kind, 'blueprint_id': blueprint_id,
                'source_kind': 'reviewed_native_asset', 'reviewer': 'test fixture',
                'review_date': '2026-11-27', 'classification_conclusion': kind,
                'power_source_evidence': source.name + ': synthetic power fixture',
                'device_geometry_evidence': source.name + ': synthetic geometry fixture',
                'source_refs': [{'path': source.name,
                                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
            }
        self.library = BothLibrary([row['blueprint_id'] for row in self.reviews.values()])

    def test_all_four_exact_inputs_and_controlled_pairs(self):
        plan = build(self.library, self.reviews, self.root)
        self.assertEqual(len(plan['cases']), 4)
        self.assertEqual(len(plan['comparisons']), 2)
        self.assertFalse(plan['selected_for_delivery'])
        self.assertTrue(all(not case['physical_acceptance_claimed'] for case in plan['cases']))
        self.assertTrue(all(case['recorded_frames'] == 600 and
                            case['rate_hz'] == 20 and len(case['cameras']) == 4
                            for case in plan['cases']))
        self.assertEqual({c['machine_class'] for c in plan['cases']},
                         {'electric_bicycle', 'electric_scooter'})
        self.assertTrue(all(len(row['case_ids']) == 2 for row in plan['comparisons']))

    def test_missing_class_and_relabeled_ordinary_bicycle_fail(self):
        with self.assertRaisesRegex(ValueError, 'Both exact'):
            build(self.library, {'electric_bicycle': self.reviews['electric_bicycle']}, self.root)
        bad = dict(self.reviews['electric_scooter'], blueprint_id='vehicle.bh.crossbike')
        with self.assertRaisesRegex(ValueError, 'Ordinary bicycle'):
            build(self.library, {**self.reviews, 'electric_scooter': bad}, self.root)

    def test_missing_live_asset_or_stale_source_fail(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            build(BothLibrary(['vehicle.reviewed.ebike']), self.reviews, self.root)
        bad = dict(self.reviews['electric_scooter'])
        bad['source_refs'] = [dict(bad['source_refs'][0], sha256='0' * 64)]
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            build(self.library, {**self.reviews, 'electric_scooter': bad}, self.root)

    def test_one_asset_cannot_claim_both_classes(self):
        bad = dict(self.reviews['electric_scooter'],
                   blueprint_id=self.reviews['electric_bicycle']['blueprint_id'])
        with self.assertRaisesRegex(ValueError, 'Distinct electric device'):
            build(self.library, {**self.reviews, 'electric_scooter': bad}, self.root)
