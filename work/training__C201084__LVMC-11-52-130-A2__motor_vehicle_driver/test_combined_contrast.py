"""Protect combined-manifest proof binding against stale receipts."""
import copy
import unittest
from unittest.mock import patch

import audit_combined_contrast as binding


class CombinedContrastTest(unittest.TestCase):
    def test_current_chain_binds(self):
        result = binding.audit()
        self.assertTrue(result['passed'])
        self.assertEqual(set(result['fallback_offline_selection_sha256']),
                         {'fallback1', 'fallback2', 'fallback3'})
        self.assertFalse(result['delivery_selected'])

    def test_stale_combined_manifest_rejected(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-combined-contrast-primary-offline-selection.json'):
                value = copy.deepcopy(value)
                value['manifest_sha256'] = '0' * 64
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'offline selection differs'):
                binding.audit()

    def test_fallback1_saved_source_tampering_rejected(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-combined-contrast-fallback1-saved.log'):
                value = copy.deepcopy(value)
                value['original_source_hashes']['native-actors.jsonl'] = '0' * 64
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'fallback1 retained source differs'):
                binding.audit()


if __name__ == '__main__':
    unittest.main()
