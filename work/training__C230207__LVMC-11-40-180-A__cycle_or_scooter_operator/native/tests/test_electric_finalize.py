"""Saved-only electric source binding tests; generated data is not a recording."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from electric_finalize import validate_electric_recording
from electric_asset import review_digest


class ElectricFinalizeTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[4] / '.runtime-work' / 'c230207-electric-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'asset-source.txt'
        source.write_text('Synthetic class and power review fixture only.\n')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.config = {'machine_class': 'electric_scooter',
                       'rider_class': 'electric_scooter',
                       'electric_asset_source_root': str(self.root),
                       'electric_asset_review': {
                           'machine_class': 'electric_scooter',
                           'blueprint_id': 'vehicle.reviewed.escooter',
                           'source_refs': [{'path': source.name, 'sha256': digest}]}}
        self.context = {'blueprint_id': 'vehicle.reviewed.escooter',
                        'electric_asset_binding': {
                            'machine_class': 'electric_scooter',
                            'blueprint_id': 'vehicle.reviewed.escooter',
                            'native_actor_id': 42,
                            'classification_review_bound': True,
                            'review_source_sha256': {source.name: digest},
                            'review_sha256': review_digest(self.config['electric_asset_review'])}}
        self.row = {'machine_class': 'electric_scooter',
                    'electric_asset_blueprint_id': 'vehicle.reviewed.escooter',
                    'rider_blueprint_id': 'vehicle.reviewed.escooter',
                    'rider_actor_id': 42}
        self.write_sources()

    def write_sources(self, count=600):
        (self.root / 'config.json').write_text(json.dumps(self.config) + '\n')
        (self.root / 'restriction-context.json').write_text(json.dumps(self.context) + '\n')
        (self.root / 'bicycle-poses.jsonl').write_text(
            ''.join(json.dumps(self.row) + '\n' for _ in range(count)))

    def test_positive_original_actor_and_source_join(self):
        binding = validate_electric_recording(self.root)
        self.assertEqual(binding['native_actor_id'], 42)
        self.assertFalse(binding['original_class_pixels_verified'])
        self.assertFalse(binding['physical_acceptance_claimed'])

    def test_stale_review_and_missing_asset_source_rejected(self):
        source = self.root / 'asset-source.txt'
        source.write_text('Changed fixture.\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            validate_electric_recording(self.root)
        source.unlink()
        with self.assertRaisesRegex(ValueError, 'source unavailable'):
            validate_electric_recording(self.root)

    def test_actor_and_class_substitution_rejected(self):
        self.row['rider_actor_id'] = 43
        self.write_sources()
        with self.assertRaisesRegex(ValueError, 'pose and reviewed asset binding differ'):
            validate_electric_recording(self.root)
        self.row['rider_actor_id'] = 42
        self.config['rider_class'] = 'human_propelled_bicycle'
        self.write_sources()
        with self.assertRaisesRegex(ValueError, 'Exact electric class'):
            validate_electric_recording(self.root)

    def test_short_source_rejected(self):
        self.write_sources(count=599)
        with self.assertRaisesRegex(ValueError, '600-frame'):
            validate_electric_recording(self.root)
