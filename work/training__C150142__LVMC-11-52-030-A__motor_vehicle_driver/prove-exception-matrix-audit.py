"""Exercise the exception matrix audit's missing and altered evidence branches."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('exception_audit',ROOT/'audit-exception-matrix.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MatrixAuditProof(unittest.TestCase):
    def setUp(self):
        self.matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())

    def test_positive_and_missing_case(self):
        self.assertTrue(module.audit(self.matrix)['passed'])
        changed=copy.deepcopy(self.matrix)
        changed['cases']=[c for c in changed['cases']
                          if not c['case_id'].endswith('__rtc_bus_at')]
        with self.assertRaisesRegex(ValueError,'branch count'):
            module.audit(changed)

    def test_boundary_and_legal_claim_rejected(self):
        changed=copy.deepcopy(self.matrix)
        next(c for c in changed['cases'] if c['case_id'].endswith('__limo_at'))[
            'requested_stationary_duration_s']=1799.9
        with self.assertRaisesRegex(ValueError,'Thirty-minute boundary'):
            module.audit(changed)
        changed=copy.deepcopy(self.matrix)
        changed['cases'][0]['legal_verdict']='compliant'
        with self.assertRaisesRegex(ValueError,'legal outcome'):
            module.audit(changed)

    def test_uncontrolled_comparison_rejected(self):
        changed=copy.deepcopy(self.matrix)
        changed['comparisons'][0]['fixed_conditions']=[]
        with self.assertRaisesRegex(ValueError,'controlled comparison'):
            module.audit(changed)

if __name__=='__main__':unittest.main()
