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
                "building_use_source", "freight_zone_source", "route_source",
                "driver_source", "camera_rig_source", "weather_source")}
    context.update(district_kind=district, maneuver="left_turn")
    rows = [{"frame": i, "time_s": i * .05, "x_m": i * spacing_m,
             "y_m": 0.0, "left_signal": i >= start,
             "course_change": i >= 5, "weather": weather}
            for i in range(6)]
    return {"format": "native-turn-signal-samples-v1",
            "source_kind": "diagnostic_fixture", "diagnostic_fixture": True,
            "case_id": case, "ego_actor": "motor_vehicle_driver",
            "context": context, "samples": rows}


class SavedMeasurementTest(unittest.TestCase):
    def test_both_statutory_references_from_saved_samples(self):
        for district, prefix, reference in (("business", "business", 100),
                                            ("residential", "residence", 100),
                                            ("other", "other_area", 300)):
            case = "a__" + prefix + "_at_" + str(reference) + "ft"
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
            for tag, first in (("business_short", 1),
                               ("business_at_100ft", 0),
                               ("business_continuous", 0)):
                case = "a__" + tag
                source = root / (tag + ".json")
                source.write_text(json.dumps(packet(case, "business", first, 7.0)) + "\n")
                readings.append(measure(source, case))
            with self.assertRaisesRegex(ValueError, "above-boundary measured contrast missing"):
                compare(*readings[:2], "business_left_turn_distance", readings[2])
            changed = dict(readings[2], context_sources={"route_source": "changed"})
            with self.assertRaisesRegex(ValueError, "fixed context differs"):
                compare(readings[0], changed, "business_left_turn_distance")


if __name__ == "__main__":
    unittest.main()
