import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import capture
from saved_sight import SavedSightError, verify
from test_native_sight_capture import Ego, World, rays, route
from test_sight import site

CASE = "testing__C111278__LVMC-11-16-040__motor_vehicle_driver__blocked_at"


class SavedSightTests(unittest.TestCase):
    def make_attempt(self, root):
        output = Path(root) / "attempt"
        capture("blocked_at", site(), World(), Ego(), route, rays, lambda ego: None, output)
        return output

    def test_saved_remeasurement_and_case_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            attempt = self.make_attempt(root)
            result = verify(attempt, CASE)
            self.assertEqual(result["original_sight_join"], "passed")
            self.assertIsNone(result["legal_conclusion"])
            with self.assertRaises(SavedSightError):
                verify(attempt, CASE + "_other")

    def test_tamper_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            attempt = self.make_attempt(root)
            path = attempt / "native-sight.json"
            packet = json.loads(path.read_text())
            packet["frames"][140]["ego_speed_mps"] = 99
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(SavedSightError, "source changed"):
                verify(attempt, CASE)
            path.unlink()
            with self.assertRaisesRegex(SavedSightError, "absent"):
                verify(attempt, CASE)

    def test_forged_receipt_measurement_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            attempt = self.make_attempt(root)
            path = attempt / "native-sight-receipt.json"
            receipt = json.loads(path.read_text())
            receipt["measurement"]["all_views_clear"] = True
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(SavedSightError, "recomputation"):
                verify(attempt, CASE)


if __name__ == "__main__": unittest.main()
