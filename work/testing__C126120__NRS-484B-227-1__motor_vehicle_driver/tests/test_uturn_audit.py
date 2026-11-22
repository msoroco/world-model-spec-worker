import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uturn_audit import compare, load_and_measure, measure


def body(x, y):
    return [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]]


def trace():
    return {"context": {
        "map_source_sha256": "map hash", "authority_review_source_sha256": "review hash",
        "opening_id": "opening-1", "source_right_roadway_id": "south-east",
        "destination_right_roadway_id": "north-west",
        "opening_bounds_xy_m": [-1,-1,1,1],
        "closed_divider_bounds_xy_m": [[-4,-1,-1.1,1],[1.1,-1,4,1]],
        "source_right_roadway_bounds_xy_m": [-4,-4,4,-1.2],
        "destination_right_roadway_bounds_xy_m": [-4,1.2,4,4],
        "opposite_non_right_roadway_bounds_xy_m": [-4,.2,4,.8]},
        "samples": [
            {"frame": i, "time_s": i/20, "body_vertices_xy_m": body(x,y),
             "heading_deg": heading, "velocity_xy_mps": velocity}
            for i,(x,y,heading,velocity) in enumerate([
                (2,-2,0,[1,0]), (1,-1.5,45,[.5,.5]),
                (0,0,90,[0,1]), (-1,1.5,135,[-.5,.5]),
                (-2,2,180,[-1,0])])]
    }


def multiple_variant():
    variant = trace()
    variant["samples"][1]["body_vertices_xy_m"] = body(0,0)
    variant["samples"][1]["heading_deg"] = 90
    variant["samples"][1]["velocity_xy_mps"] = [0,1]
    variant["samples"][2]["body_vertices_xy_m"] = body(1.5,-.5)
    variant["samples"][2]["velocity_xy_mps"] = [0,-1]
    return variant


class UTurnAuditTests(unittest.TestCase):
    def test_opening_departure_and_orientation_are_physical_only(self):
        result = measure(trace())
        self.assertTrue(result["engineering_crossing_observed"])
        self.assertTrue(result["u_turn_orientation_observed"])
        self.assertEqual(result["net_heading_change_deg"],180)
        self.assertFalse(result["multiple_movement_observed"])
        self.assertEqual(result["legal_judgment"],"unresolved")

    def test_closed_divider_contact_and_reverse_motion_are_separate(self):
        variant = multiple_variant()
        result = measure(variant)
        self.assertFalse(result["engineering_crossing_observed"])
        self.assertTrue(result["multiple_movement_observed"])
        self.assertEqual(result["closed_divider_contact_frames"],[2])

    def test_pause_or_reverse_telemetry_without_displacement_is_not_multiple_movement(self):
        paused = trace()
        paused["samples"][2]["velocity_xy_mps"] = [0,0]
        self.assertFalse(measure(paused)["multiple_movement_observed"])
        claimed_reverse = trace()
        claimed_reverse["samples"][2]["velocity_xy_mps"] = [0,-1]
        self.assertFalse(measure(claimed_reverse)["multiple_movement_observed"])

    def test_opening_touch_without_crossing_through_it_is_not_completion(self):
        bypass = trace()
        positions = [(2,-2),(0,-.8),(-5,-1.5),(-5,1.5),(-2,2)]
        for row,(x,y) in zip(bypass["samples"],positions):
            row["body_vertices_xy_m"] = body(x,y)
        observed = measure(bypass)
        self.assertTrue(observed["opening_contact_frames"])
        self.assertTrue(observed["opening_full_body_frames"])
        self.assertTrue(observed["destination_right_roadway_departure_observed"])
        self.assertFalse(observed["engineering_crossing_observed"])
        self.assertFalse(any(item["through_opening"] for item in
                             observed["roadway_centerline_crossings"]))

    def test_source_hash_and_fixed_map_comparison(self):
        baseline = trace()
        variant = multiple_variant()
        with TemporaryDirectory() as directory:
            path = Path(directory)/"original.json"
            path.write_text(json.dumps(baseline))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(load_and_measure(path,digest)["multiple_movement_observed"])
            with self.assertRaisesRegex(ValueError,"hash mismatch"):
                load_and_measure(path,"wrong")
        self.assertTrue(compare(baseline,variant,["multiple_movement_observed"])["right"]["multiple_movement_observed"])
        variant["context"]["map_source_sha256"] = "different"
        with self.assertRaisesRegex(ValueError,"fixed OpenDRIVE"):
            compare(baseline,variant,["multiple_movement_observed"])
        variant = multiple_variant()
        variant["context"]["authority_review_source_sha256"] = "other authority packet"
        with self.assertRaisesRegex(ValueError,"fixed comparison context changed"):
            compare(baseline,variant,["multiple_movement_observed"])


if __name__ == "__main__": unittest.main()
