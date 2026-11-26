import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_accepted import review
import test_original_source_audit as source_tests


RECORDING = "49dc501d992043846016690541d4ac23b3b3af4faaae54cad7af07f5e035c6b8"
CASE = "testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__above"


class AcceptedReviewTests(unittest.TestCase):
    def attempt(self, root):
        case, inventory = source_tests.SourceDeliveryTests().make_attempt(root)
        self.assertEqual(case, CASE)
        inventory["recording_id"] = RECORDING
        (root / "inventory.json").write_text(json.dumps(inventory) + "\n")

    def test_retained_identity_and_source_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.attempt(root)
            receipt = review(root, CASE)
            self.assertFalse(receipt["law_coverage_confirmed"])
            self.assertEqual(receipt["recording_id"], RECORDING)

    def test_missing_original_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "source inventory missing"):
                review(Path(directory), CASE)

    def test_wrong_original_recording_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.attempt(root)
            inventory = json.loads((root / "inventory.json").read_text())
            inventory["recording_id"] = "unrelated"
            (root / "inventory.json").write_text(json.dumps(inventory) + "\n")
            with self.assertRaisesRegex(ValueError, "recording identity"):
                review(root, CASE)
