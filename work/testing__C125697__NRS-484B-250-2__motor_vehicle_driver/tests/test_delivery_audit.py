import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_delivery', ROOT / 'audit_delivery.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeliveryAuditTests(unittest.TestCase):
    def test_twenty_source_bound_saved_proofs(self):
        report = module.audit()
        self.assertEqual(report['exact_constructions'], 20)
        self.assertFalse(report['physical_acceptance_claimed'])

    def test_missing_compatibility_and_saved_proofs_rejected(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        result = json.loads((ROOT / 'result.json').read_text())
        broken = copy.deepcopy(manifest)
        broken['cases'][-1]['candidates'][0]['compatibility']['receipt'] = 'absent.json'
        with self.assertRaisesRegex(ValueError, 'Missing positive/negative'):
            module.audit(manifest=broken, result=result)
        result = copy.deepcopy(result)
        result['tests'] = [row for row in result['tests']
                           if row.get('log') != 'opposite-fallback3-bound-saved-v1.log']
        with self.assertRaisesRegex(ValueError, 'Missing recorded-only saved proof'):
            module.audit(manifest=manifest, result=result)

    def test_duplicate_fallback_trigger_rejected(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        result = json.loads((ROOT / 'result.json').read_text())
        broken = copy.deepcopy(manifest)
        broken['cases'][-1]['candidates'][1]['changed_knobs'] = broken['cases'][-1]['candidates'][0]['changed_knobs']
        with self.assertRaisesRegex(ValueError, 'Distinct physical-risk'):
            module.audit(manifest=broken, result=result)


if __name__ == '__main__':
    unittest.main()
