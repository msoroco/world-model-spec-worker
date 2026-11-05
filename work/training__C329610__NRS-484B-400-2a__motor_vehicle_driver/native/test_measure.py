"""Positive and adversarial saved-geometry checks; no CARLA execution."""
import json
from pathlib import Path
import tempfile
import unittest

from measure import measure


def row(t, x, y, yaw=0):
    return {"time_s": t, "native_center_xy_m": [x, y], "native_yaw_deg": yaw,
            "native_body_xy_m": [[x-2.6,y-1.1],[x-2.6,y+1.1],
                                 [x+2.6,y+1.1],[x+2.6,y-1.1]]}


class SavedGeometryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.samples = self.root / "native_samples.jsonl"
        self.geometry = self.root / "road_geometry.json"
        self.samples.write_text("\n".join(json.dumps(item) for item in
                                [row(0,-20,-1.75),row(.05,-10,-1.75),row(.1,-8,-1.75),row(.15,1.75,12,90)]) + "\n")
        self.geometry.write_text(json.dumps({"approach_direction":"eastbound",
            "destination_direction":"northbound", "approach_opposing_direction":"westbound",
            "destination_opposing_direction":"southbound", "native_map_sha256":"a"*64,
            "centerline_y_m":0,
            "right_edge_y_m":-7,"intersection_entry_x_m":-7,
            "destination_exit_y_m":7}))

    def test_positive_measurement_with_entry_bracket(self):
        result = measure(self.samples,self.geometry)
        self.assertEqual(result["approach_sample_count"],2)
        self.assertEqual(result["intersection_entry_time_bracket_s"],[.05,.1])
        self.assertEqual(result["center_to_centerline_offset_m"]["mean"],1.75)
        self.assertTrue(result["full_body_within_right_half_on_sampled_approach"])
        self.assertTrue(result["northbound_exit_observed"])

    def test_missing_native_source_rejected(self):
        self.samples.unlink()
        with self.assertRaisesRegex(ValueError,"Missing required source: native_samples.jsonl"):
            measure(self.samples,self.geometry)

    def test_wrong_direction_rejected(self):
        data=json.loads(self.geometry.read_text());data["approach_direction"]="westbound"
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"Native direction survey differs"):
            measure(self.samples,self.geometry)

    def test_missing_opposing_direction_rejected(self):
        data=json.loads(self.geometry.read_text());data["destination_opposing_direction"]=""
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"Native two-way highway evidence missing"):
            measure(self.samples,self.geometry)

    def test_no_turn_entry_rejected(self):
        self.samples.write_text("\n".join(json.dumps(item) for item in
                                [row(0,-20,-1.75),row(.05,-19,-1.75)]) + "\n")
        with self.assertRaisesRegex(ValueError,"No observed approach and intersection entry bracket"):
            measure(self.samples,self.geometry)


if __name__ == "__main__":
    unittest.main()
