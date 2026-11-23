"""Guard combined lead-presence audit against stale saved receipts."""
import copy
import unittest
from unittest.mock import patch

import audit_combined_traffic_pair as binding


class CombinedTrafficPairTest(unittest.TestCase):
    def test_combined_pair_passes(self):
        result = binding.audit()
        self.assertTrue(result['passed'])
        self.assertFalse(result['canonical_comparison_audit'])

    def test_stale_group_saved_receipt_rejected(self):
        original = binding.load

        def altered(path):
            value = original(path)
            if str(path).endswith('current-combined-near_lead-binding-audit.json'):
                value = copy.deepcopy(value)
                value['candidate_proofs']['primary']['saved_receipt_sha256'] = '0' * 64
            return value

        with patch.object(binding, 'load', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'combined group receipt differs'):
                binding.audit()


if __name__ == '__main__':
    unittest.main()
