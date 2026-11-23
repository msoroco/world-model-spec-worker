"""Independent geometry consistency proof and altered-result rejection."""

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from geometry_audit import audit
from saved_measurement import finalize_attempt
import test_saved_measurement as fixture_module


class GeometryAuditTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.SavedMeasurementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.attempt = fixture.attempt
        finalize_attempt(self.attempt, self.attempt / "analysis-report.json")

    def test_original_geometry_agrees_with_saved_observation(self):
        result = audit(self.attempt)
        self.assertEqual(result["two_queue_aligned_frame_count"], 0)
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_resealed_inflated_queue_measurement_rejected(self):
        path = self.attempt / "result.json"
        result = json.loads(path.read_text())
        result["realized_observables"]["two_queue_aligned_frame_count"] = 900
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "measurement differs"):
            audit(self.attempt)


if __name__ == "__main__":
    unittest.main()
