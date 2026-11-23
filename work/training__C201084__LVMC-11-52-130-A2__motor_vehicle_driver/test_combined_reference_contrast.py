"""Guard the combined comparison against unsupported source-review claims."""
import copy
import unittest
from unittest.mock import patch

import audit_combined_reference_contrast as binding


class CombinedComparisonTest(unittest.TestCase):
    def test_current_binding(self):
        result = binding.audit()
        self.assertTrue(result['passed'])
        self.assertFalse(result['accepted'])
        self.assertEqual(set(result['case_bindings']), {'reference', 'contrast'})

    def test_unproved_posting_rejected(self):
        original = binding.read

        def altered(path):
            value = original(path)
            if str(path).endswith('current-contrast-posting-binding.json'):
                value = copy.deepcopy(value)
                value['fire_code_designation_verified'] = True
            return value

        with patch.object(binding, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'original review overclaims'):
                binding.audit()


if __name__ == '__main__':
    unittest.main()
