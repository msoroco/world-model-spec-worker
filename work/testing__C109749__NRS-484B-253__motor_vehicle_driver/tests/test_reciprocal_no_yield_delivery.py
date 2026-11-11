import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
SOURCE = REPO / '.runtime-work/c109749-reciprocal-no-yield-fixture-v1'
OTHER = REPO / '.runtime-work/c109749-seven-case-reciprocal_continues_after_turn-primary-compat-v1'
spec = importlib.util.spec_from_file_location('reciprocal_no_yield_delivery_audit',
                                              ROOT / 'cases/reciprocal_no_yield/delivery_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate_entry_during_turn = module.validate_entry_during_turn


class ReciprocalNoYieldDeliveryTests(unittest.TestCase):
    def check(self, source, result):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('intersection_geometry.json', 'interaction_history.jsonl'):
                shutil.copyfile(source/name, root/name)
            return validate_entry_during_turn(root, result)

    def test_entry_and_saved_values_agree(self):
        result = {'measured_values': {'later_opposing_entry_frame':38039,
                  'ego_exit_frame':38040,'reciprocal_stopped_outside_during_turn':False}}
        measured = self.check(SOURCE, result)
        self.assertEqual(measured['later_opposing_entry_frame'], 38039)
        self.assertFalse(measured['legal_verdict_asserted'])

    def test_continued_outside_approach_rejected(self):
        result = {'measured_values': {'later_opposing_entry_frame':38039,
                  'ego_exit_frame':38040,'reciprocal_stopped_outside_during_turn':False}}
        with self.assertRaisesRegex(ValueError, 'entry during subject turn missing'):
            self.check(OTHER, result)

    def test_spoofed_saved_entry_rejected(self):
        result = {'measured_values': {'later_opposing_entry_frame':38038,
                  'ego_exit_frame':38040,'reciprocal_stopped_outside_during_turn':False}}
        with self.assertRaisesRegex(ValueError, 'differ from original'):
            self.check(SOURCE, result)


if __name__ == '__main__':
    unittest.main()
