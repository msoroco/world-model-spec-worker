import unittest
from runner import check
from finalize import derive
class ExactSchoolWarning(unittest.TestCase):
 def test_selected_native_request(self):
  self.assertEqual(check()['pair']['frames'],600)
  self.assertFalse(check()['original_native_observed'])
 def test_missing_original_source_rejected(self):
  with self.assertRaisesRegex(ValueError,'Missing sealed original'):
   derive('.')
