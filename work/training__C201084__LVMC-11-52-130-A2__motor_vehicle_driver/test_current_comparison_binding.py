"""Check that current diagnostic comparison receipts bind to saved sources."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_current_reference_contrast as binding


ATTEMPT = Path('.runtime-work/c201084-reference-current-primary-compatibility')


class CurrentComparisonBindingTests(unittest.TestCase):
    def test_current_primary_receipts_bind(self):
        result = binding.bind_case('reference', ATTEMPT)
        self.assertEqual(result['source_sha256']['native-actors.jsonl'],
                         binding.read(binding.HERE /
                                      'current-reference-primary-saved-receipt.json')
                         ['original_source_hashes']['native-actors.jsonl'])
        self.assertIn('saved_receipt_sha256', result)

    def test_rejects_saved_source_mismatch(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-reference-primary-saved-receipt.json'):
                value = copy.deepcopy(value)
                value['original_source_hashes']['native-actors.jsonl'] = '0' * 64
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'source/saved binding differs'):
                binding.bind_case('reference', ATTEMPT)

    def test_rejects_unverified_posting_claim(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-reference-posting-binding.json'):
                value = copy.deepcopy(value)
                value['fire_code_designation_verified'] = True
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'posting review overclaims'):
                binding.bind_case('reference', ATTEMPT)


if __name__ == '__main__':
    unittest.main()
