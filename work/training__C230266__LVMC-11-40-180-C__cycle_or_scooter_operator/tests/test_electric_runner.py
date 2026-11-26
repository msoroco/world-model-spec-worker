"""CPU checks for the conditional electric-device Native entrypoint."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE / 'native'))
from electric_runner import check


class ElectricRunnerChecks(unittest.TestCase):
    def test_exact_source_bound_classes_and_rejections(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as folder:
            source = Path(folder) / 'device.uasset'
            source.write_bytes(b'CPU fixture, not a real electric asset')
            baseline = json.loads((PACKAGE / 'config.json').read_text())
            for device_class in ('electric_bicycle', 'electric_scooter'):
                with self.subTest(device_class=device_class):
                    config = {**baseline,
                              'device_class': device_class,
                              'device_blueprint_filter': 'vehicle.custom.' + device_class,
                              'source_bound_blueprint_id': 'vehicle.custom.' + device_class,
                              'native_asset_source': str(source),
                              'native_asset_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
                    self.assertEqual(check(config)['frames'], 600)
                    with self.assertRaisesRegex(ValueError, 'source/hash'):
                        check({**config, 'native_asset_sha256': '0' * 64})
                    with self.assertRaisesRegex(ValueError, 'source inventory'):
                        check({**config, 'source_bound_blueprint_id': 'vehicle.other'})
                    with self.assertRaisesRegex(ValueError, 'class required'):
                        check({**config, 'device_class': 'ordinary_bicycle'})


if __name__ == '__main__':
    unittest.main()
