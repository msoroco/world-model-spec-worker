import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection_measurement import ASSIGNMENT, LIMIT_M, measure


class ProjectionTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "curb_segment_start_m": [0, 0], "curb_segment_end_m": [10, 0],
                "street_side_reference_m": [0, 5], "load_present": False, "trailer_attached": False,
                "physical_parts": [{"category": "vehicle", "source_actor_id": "ego",
                                    "outline_vertices_m": [[1, 0], [3, 0], [3, 4], [1, 4]]}]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_vehicle_below_limit(self):
        r = self.run_measure(self.packet())
        self.assertAlmostEqual(r["maximum_street_projection_m"], 4)
        self.assertFalse(r["exceeds_fifteen_feet"])
        self.assertAlmostEqual(LIMIT_M, 4.572)

    def test_load_tip_controls(self):
        p = self.packet()
        p["load_present"] = True
        p["physical_parts"].append({"category": "load", "source_actor_id": "load-1",
                                    "outline_vertices_m": [[1, 3], [2, 3], [2, 5]]})
        r = self.run_measure(p)
        self.assertTrue(r["exceeds_fifteen_feet"])
        self.assertAlmostEqual(r["maximum_street_projection_m"], 5)

    def test_trailer_presence_requires_outline(self):
        p = self.packet()
        p["trailer_attached"] = True
        with self.assertRaisesRegex(ValueError, "trailer attachment"):
            self.run_measure(p)

    def test_reverse_curb_direction_same_projection(self):
        p = self.packet()
        p["curb_segment_start_m"], p["curb_segment_end_m"] = p["curb_segment_end_m"], p["curb_segment_start_m"]
        self.assertAlmostEqual(self.run_measure(p)["maximum_street_projection_m"], 4)

    def test_ambiguous_street_side_rejected(self):
        p = self.packet()
        p["street_side_reference_m"] = [5, 0]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
