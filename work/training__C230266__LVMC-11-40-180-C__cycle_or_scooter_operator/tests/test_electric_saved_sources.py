"""Source binding checks for pending electric saved processing."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE / 'native'))
from finalize import validate_electric_sources


class ElectricSavedSourceChecks(unittest.TestCase):
    def test_exact_type_power_and_actor_binding(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as folder:
            attempt = Path(folder)
            for device_class in ('electric_bicycle', 'electric_scooter'):
                with self.subTest(device_class=device_class):
                    sources = {}
                    config = {'device_class': device_class,
                              'source_bound_blueprint_id': 'vehicle.custom.' + device_class}
                    for prefix in ('native_asset', 'legal_class', 'device_type', 'motor_power'):
                        path = attempt / (prefix + '.txt')
                        path.write_text('synthetic ' + prefix + ' source')
                        digest = hashlib.sha256(path.read_bytes()).hexdigest()
                        config[prefix + '_source'] = str(path)
                        config[prefix + '_sha256'] = digest
                        sources[prefix] = digest
                    evidence = {'source_kind': 'original_native_electric_device_binding',
                                'device_class_requested': device_class,
                                'blueprint_id': config['source_bound_blueprint_id'],
                                'actor_id': 42, 'source_hashes': sources}
                    (attempt / 'electric-device-evidence.json').write_text(json.dumps(evidence))
                    (attempt / 'sidewalk-actors.jsonl').write_text(json.dumps({
                        'rider_id': 42,
                        'rider_device_blueprint': config['source_bound_blueprint_id']}) + '\n')
                    self.assertEqual(validate_electric_sources(attempt, config)[
                        'device_class_requested'], device_class)
                    with self.assertRaisesRegex(ValueError, 'motor_power source/hash'):
                        validate_electric_sources(attempt, {
                            **config, 'motor_power_sha256': '0' * 64})
                    (attempt / 'electric-device-evidence.json').unlink()
                    with self.assertRaisesRegex(ValueError, 'Missing required source'):
                        validate_electric_sources(attempt, config)


if __name__ == '__main__':
    unittest.main()
