import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_delivery_audit import fixture


MODULE = Path(__file__).resolve().parents[1] / 'comparison_delivery.py'
spec = importlib.util.spec_from_file_location('trail_comparison_delivery', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
SCRATCH = MODULE.parents[2] / '.runtime-work' / 'c143687-comparison-tests'


def original_fixture(root, case):
    root.mkdir()
    inventory, data = fixture(root, case)
    data['provenance_kind'] = 'original_native'
    data['diagnostic_fixture'] = False
    inventory.write_text(json.dumps(data), encoding='utf-8')
    return inventory, data


class ComparisonDeliveryTests(unittest.TestCase):
    def test_all_five_exact_saved_pairs(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            base = Path(tmp) / 'base'
            original_fixture(base, 'all_prerequisites')
            for comparison_id, (case, variable) in audit.COMPARISONS.items():
                variant = Path(tmp) / case
                original_fixture(variant, case)
                with self.subTest(comparison=comparison_id):
                    result = audit.audit_comparison(comparison_id, base, variant)
                    self.assertEqual(result['deliberate_difference'], variable)
                    self.assertEqual(len(result['acquisition_sha256']), 2)
                    self.assertFalse(result['physical_video_visibility_verified'])
                    self.assertIsNone(result['legal_judgment'])

    def test_rejects_unbound_source_and_wrong_provenance(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            base, variant = Path(tmp) / 'base', Path(tmp) / 'variant'
            original_fixture(base, 'all_prerequisites')
            path, data = original_fixture(variant, 'not_designated')
            with self.assertRaisesRegex(ValueError, 'two distinct saved attempts'):
                audit.audit_comparison('trail_not_designated', base, base)
            data['diagnostic_fixture'] = True
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'original acquisition provenance missing'):
                audit.audit_comparison('trail_not_designated', base, variant)
            data['diagnostic_fixture'] = False
            path.write_text(json.dumps(data), encoding='utf-8')
            (variant / 'overview.mp4').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError, 'overview camera hash mismatch'):
                audit.audit_comparison('trail_not_designated', base, variant)

    def test_rejects_fixed_condition_change(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            base, variant = Path(tmp) / 'base', Path(tmp) / 'variant'
            original_fixture(base, 'all_prerequisites')
            path, data = original_fixture(variant, 'not_designated')
            history = variant / data['history']['path']
            rows = [json.loads(line) for line in history.read_text().splitlines()]
            for row in rows:
                row['map_sha256'] = 'other-map'
            raw = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
            history.write_bytes(raw)
            import hashlib
            data['history']['sha256'] = hashlib.sha256(raw).hexdigest()
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fixed condition changed: map_sha256'):
                audit.audit_comparison('trail_not_designated', base, variant)


if __name__ == '__main__':
    unittest.main()
