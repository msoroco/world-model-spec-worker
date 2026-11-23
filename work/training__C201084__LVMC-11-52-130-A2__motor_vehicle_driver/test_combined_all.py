"""Guard full combined CPU coverage against a stale group receipt."""
import copy
import unittest
from unittest.mock import patch

import audit_combined_all as binding


class CombinedAllTest(unittest.TestCase):
    def test_all_eight_groups_pass(self):
        result = binding.audit()
        self.assertEqual(result['candidate_chains_passed'], 32)
        self.assertEqual(set(result['case_group_binding_sha256']), set(binding.GROUPS))
        self.assertFalse(result['delivery_selected'])

    def test_stale_group_receipt_rejected(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-combined-clear-binding-audit.json'):
                value = copy.deepcopy(value)
                value['candidate_proofs']['fallback3']['saved_receipt_sha256'] = '0' * 64
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Combined group audit differs'):
                binding.audit()


if __name__ == '__main__':
    unittest.main()
