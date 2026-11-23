"""Guard combined group binding against stale manifest and source receipts."""
import copy
import unittest
from unittest.mock import patch

import audit_combined_groups as binding


class CombinedGroupsTest(unittest.TestCase):
    def test_conflict_current_chain(self):
        result = binding.audit_group('conflict')
        self.assertTrue(result['passed'])
        self.assertEqual(set(result['candidate_proofs']),
                         {'primary', 'fallback1', 'fallback2', 'fallback3'})
        self.assertFalse(result['delivery_selected'])

    def test_stale_fallback_source_rejected(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-combined-conflict-fallback2-saved.log'):
                value = copy.deepcopy(value)
                value['original_source_hashes']['native-actors.jsonl'] = '0' * 64
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'retained source differs'):
                binding.audit_group('conflict')


if __name__ == '__main__':
    unittest.main()
