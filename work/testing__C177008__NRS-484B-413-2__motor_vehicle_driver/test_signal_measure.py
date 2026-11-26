"""Saved-sample fixture tests; no original recording or legal verdict is claimed."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from signal_measure import compare, measure


def packet(case: str, district: str, start: int, spacing_m: float,
           weather: str = "clear") -> dict:
    context = {name: "diagnostic-" + name for name in
               ("highway_source", "district_source", "frontage_source",
                "building_use_source", "other_vehicle_source", "route_source",
                "driver_source", "camera_rig_source", "weather_source")}
    context.update(district_kind=district, maneuver="right_turn")
    rows = [{"frame": i, "time_s": i * .05, "x_m": i * spacing_m,
             "y_m": 0.0, "right_signal": i >= start,
             "course_change": i >= 5, "weather": weather}
            for i in range(6)]
    return {"format": "native-turn-signal-samples-v1",
            "source_kind": "diagnostic_fixture", "diagnostic_fixture": True,
            "case_id": case, "ego_actor": "motor_vehicle_driver",
            "context": context, "samples": rows}


class SavedMeasurementTest(unittest.TestCase):
    def test_both_statutory_references_from_saved_samples(self):
        for district, suffix, reference in (("business", "business_sufficient", 100),
                                            ("other", "other_area_short", 300)):
            case = "a__" + suffix
            with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
                source = Path(temporary) / "signal.json"
                source.write_text(json.dumps(packet(case, district, 0,
                                                    reference * .3048 * 1.01 / 5)) + "\n")
                result = measure(source, case)
                self.assertEqual(result["statutory_reference_ft"], reference)
                self.assertTrue(result["sampled_threshold_reached"])

    def test_comparison_rejects_changed_fixed_context(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            root = Path(temporary)
            readings = []
            for tag, first in (("business_sufficient", 0),
                               ("business_short", 2)):
                case = "a__" + tag
                source = root / (tag + ".json")
                source.write_text(json.dumps(packet(case, "business", first, 7.0)) + "\n")
                readings.append(measure(source, case))
            self.assertTrue(compare(readings[0], readings[1], "lead_distance")["software_measurement_passed"])
            changed = dict(readings[1], context_sources={"route_source": "changed"})
            with self.assertRaisesRegex(ValueError, "fixed Native site or context differs"):
                compare(readings[0], changed, "lead_distance")


if __name__ == "__main__":
    unittest.main()
