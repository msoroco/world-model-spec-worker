"""Exact Native case configuration uses the original body history."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from case_builder import config
from runner import check_scene
from test_uturn_control import scene


class CaseBuilderTests(unittest.TestCase):
    def test_exact_case_and_multiple_movement_target(self):
        item = scene()
        item["context"]["opening_id"] = "opening-1"
        item["context"]["source_right_roadway_id"] = "east-right"
        item["context"]["destination_right_roadway_id"] = "west-right"
        item["divider_props"] = [
            {"blueprint_id":"static.prop.barrier","bounds_xy_m":rect,"z_m":0}
            for rect in item["context"]["closed_divider_bounds_xy_m"]]
        item.update(case_id="testing__C126120__NRS-484B-227-1__motor_vehicle_driver__opening_single",
                    duration_s=10,capture_rate_hz=20,
                    reviewed_context_source="review.json",reviewed_context_sha256="source hash",
                    authority_review_source="authority.json")
        self.assertIs(check_scene(item),item)
        built = config(item)
        self.assertEqual(built["physical_completion"]["motion_source"],"ego-body-history.jsonl")
        self.assertEqual(built["physical_completion"]["criterion"],"turn")
        self.assertEqual(len(built["supported_case_ids"]),7)
        self.assertEqual([(camera["name"],camera["width"],camera["height"])
                          for camera in built["cameras"]],
                         [("overview",1920,1080),("approach",1280,720),
                          ("reference_corner",1280,720),("driver_reference",1280,720)])
        self.assertFalse(built["case"]["multiple_movement_requested"])
        item["segment_directions"] = ["forward","forward","reverse","forward"]
        self.assertTrue(config(item)["case"]["multiple_movement_requested"])
        item["case_id"] = "other_assignment__opening_single"
        with self.assertRaisesRegex(ValueError,"case ID"):
            check_scene(item)


if __name__ == "__main__":
    unittest.main()
