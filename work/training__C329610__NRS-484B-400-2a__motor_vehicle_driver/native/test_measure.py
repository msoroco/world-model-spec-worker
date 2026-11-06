"""Positive and adversarial Native-frame measurement fixtures; no CARLA run."""
import json
from pathlib import Path
import tempfile
import unittest

from measure import measure


def row(t, x, y, forward=(1,0)):
    return {"time_s": t, "native_center_xy_m": [x, y],
            "native_forward_xy": list(forward),
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
                                [row(0,-20,1.75),row(.05,-10,1.75),
                                 row(.1,-8,1.75),row(.15,1.75,-12,(0,-1))]) + "\n")
        self.geometry.write_text(json.dumps({
            "road_directions_native":{"approach_forward":[1,0],"approach_opposing":[-1,0],
                                      "destination_forward":[0,-1],"destination_opposing":[0,1]},
            "native_map_sha256":"a"*64,
            "approach_centerline_point_native_m":[0,0],
            "approach_right_normal_native":[0,1],"right_half_width_m":7,
            "intersection_entry_point_native_m":[-7,0],"approach_forward_native":[1,0],
            "destination_exit_point_native_m":[0,-7],"destination_forward_native":[0,-1]}))

    def test_positive_reflected_native_measurement(self):
        result = measure(self.samples,self.geometry)
        self.assertEqual(result["approach_sample_count"],2)
        self.assertEqual(result["intersection_entry_time_bracket_s"],[.05,.1])
        self.assertEqual(result["center_to_centerline_right_offset_m"]["mean"],1.75)
        self.assertTrue(result["full_body_within_right_half_on_sampled_approach"])
        self.assertTrue(result["destination_exit_observed"])

    def test_missing_native_source_rejected(self):
        self.samples.unlink()
        with self.assertRaisesRegex(ValueError,"Missing required source: native_samples.jsonl"):
            measure(self.samples,self.geometry)

    def test_missing_opposing_direction_rejected(self):
        data=json.loads(self.geometry.read_text());data["road_directions_native"].pop("destination_opposing")
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"Native two-way highway evidence missing"):
            measure(self.samples,self.geometry)

    def test_mismatched_turn_direction_rejected(self):
        data=json.loads(self.geometry.read_text());data["destination_forward_native"]=[0,1]
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"Native direction survey differs"):
            measure(self.samples,self.geometry)

    def test_no_turn_entry_rejected(self):
        self.samples.write_text("\n".join(json.dumps(item) for item in
                                [row(0,-20,1.75),row(.05,-19,1.75)]) + "\n")
        with self.assertRaisesRegex(ValueError,"No observed approach and intersection entry bracket"):
            measure(self.samples,self.geometry)

    def test_map_hash_absent_rejected(self):
        data=json.loads(self.geometry.read_text());data["native_map_sha256"]="unverified"
        self.geometry.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"Native map hash missing"):
            measure(self.samples,self.geometry)


if __name__ == "__main__":
    unittest.main()
