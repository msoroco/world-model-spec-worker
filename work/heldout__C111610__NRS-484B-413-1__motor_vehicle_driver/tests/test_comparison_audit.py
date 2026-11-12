import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison_audit', ROOT / 'comparison_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComparisonAuditTests(unittest.TestCase):
    def test_farther_pedestrian_source_comparison(self):
        manifest, receipts = module.load()
        result = module.inspect_clearance(manifest, receipts)
        self.assertTrue(result['passed'])
        self.assertGreater(*reversed(result['minimum_sampled_surface_gap_m']))

    def test_clearance_audit_rejects_changed_fixed_motion_and_missing_body_difference(self):
        manifest, receipts = module.load()
        bad = copy.deepcopy(receipts)
        far = bad[module.FAR]['measurement_examples']['turn_signal_observation']['value']
        far['sources']['ego_turn_motion.jsonl'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'fixed original changed'):
            module.inspect_clearance(manifest, bad)
        bad = copy.deepcopy(receipts)
        far = bad[module.FAR]['measurement_examples']['turn_signal_observation']['value']
        near = bad[module.IDS['horn']]['measurement_examples']['turn_signal_observation']['value']
        far['sources']['participant_bodies.jsonl'] = near['sources']['participant_bodies.jsonl']
        with self.assertRaisesRegex(ValueError, 'body source unchanged'):
            module.inspect_clearance(manifest, bad)

    def test_primary_source_comparisons(self):
        manifest, receipts = module.load()
        self.assertTrue(module.inspect(manifest, receipts)['passed'])

    def test_rejects_stale_construction_and_missing_horn_contrast(self):
        manifest, receipts = module.load()
        bad = copy.deepcopy(receipts)
        bad[module.IDS['no_horn']]['construction_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Stale construction binding'):
            module.inspect(manifest, bad)
        bad = copy.deepcopy(receipts)
        bad[module.IDS['no_horn']]['measurement_examples']['turn_signal_observation']['value']['max_pre_turn_listener_audio_rms'] = 0.5
        with self.assertRaisesRegex(ValueError, 'Horn contrast absent'):
            module.inspect(manifest, bad)

    def test_rejects_changed_pedestrian_path_and_allows_background_audio(self):
        manifest, receipts = module.load()
        bad = copy.deepcopy(receipts)
        no_horn = bad[module.IDS['no_horn']]['measurement_examples']['turn_signal_observation']['value']
        no_horn['sources']['participant_bodies.jsonl'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Pedestrian body path changed'):
            module.inspect(manifest, bad)
        background = copy.deepcopy(receipts)
        background[module.IDS['no_horn']]['measurement_examples']['turn_signal_observation']['value']['max_pre_turn_listener_audio_rms'] = 0.1
        self.assertTrue(module.inspect(manifest, background)['passed'])

    def test_rejects_stale_compatibility_receipt_binding(self):
        manifest, receipts = module.load()
        bad = copy.deepcopy(manifest)
        entry = next(item for item in bad['cases'] if item['case_id'] == module.IDS['horn'])
        entry['compatibility']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Stale compatibility receipt file'):
            module.inspect(bad, receipts)


if __name__ == '__main__':
    unittest.main()
