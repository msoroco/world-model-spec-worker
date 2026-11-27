"""Conditional construction preserves both device-class comparison designs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from electric_case_factory import build


class ConditionalFactoryChecks(unittest.TestCase):
    def test_six_exact_cases_and_missing_class_rejection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as folder:
            folder = Path(folder)
            assets = []
            for device_class in ('electric_bicycle', 'electric_scooter'):
                source = folder / (device_class + '.uasset')
                law = folder / (device_class + '.txt')
                source.write_text('synthetic CPU asset receipt')
                law.write_text('synthetic CPU class receipt')
                assets.append({'device_class': device_class,
                               'blueprint_id': 'vehicle.custom.' + device_class,
                               'native_asset_source': str(source),
                               'native_asset_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                               'legal_class_source': str(law),
                               'legal_class_sha256': hashlib.sha256(law.read_bytes()).hexdigest(),
                               **{prefix + '_source': str(law) for prefix in
                                   ('device_type', 'motor_power')},
                               **{prefix + '_sha256': hashlib.sha256(law.read_bytes()).hexdigest()
                                  for prefix in ('device_type', 'motor_power')},
                               'original_class_review_required': True})
            inventory = folder / 'inventory.json'
            inventory.write_text(json.dumps({'assets': assets}))
            result = build(inventory)
            self.assertFalse(result['delivery_ready'])
            self.assertEqual(len(result['cases']), 6)
            for device_class in ('electric_bicycle', 'electric_scooter'):
                group = [entry['config'] for entry in result['cases']
                         if entry['device_class'] == device_class]
                self.assertEqual(len(group), 3)
                self.assertEqual({(c['target_request']['signal_requested'],
                                   c['target_request']['pause_requested']) for c in group},
                                 {(True, True), (False, True), (True, False)})
                self.assertEqual(len({json.dumps(c['cameras'], sort_keys=True)
                                      for c in group}), 1)
                self.assertEqual({c['duration_s'] for c in group}, {30})
                self.assertEqual({c['rate_hz'] for c in group}, {20})
                self.assertEqual({len(c['supported_case_ids']) for c in group}, {6})
            inventory.write_text(json.dumps({'assets': assets[:1]}))
            with self.assertRaisesRegex(ValueError, 'Both source-bound'):
                build(inventory)


if __name__ == '__main__':
    unittest.main()
