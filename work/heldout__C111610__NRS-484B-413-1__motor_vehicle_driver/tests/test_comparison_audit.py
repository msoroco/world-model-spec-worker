import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison_audit', ROOT / 'comparison_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComparisonAuditTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
