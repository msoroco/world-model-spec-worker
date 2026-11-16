import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import heavy_physical_outcome as physical
import heavy_lifecycle_fixture as lifecycle


class HeavyPhysicalLifecycleTest(unittest.TestCase):
    def test_physical_case_events_and_missing_pixel_review(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        frames = [{"frame": 1, "time_s": 0.0, "minimum_clearance_m": 0.5,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": 0.5,
                                             "right_clearance_m": 0.5}]},
                  {"frame": 2, "time_s": 0.05, "minimum_clearance_m": -0.2,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": -0.2,
                                             "right_clearance_m": 1.2}]}]
        trace = [{"frame": 1, "time_s": 0.0, "position": {"x": 0.0, "y": 0.0}},
                 {"frame": 2, "time_s": 0.05, "position": {"x": 1.0, "y": 0.0}}]
        sources = {name: name for name in ("native_three_lane_survey.json",
                    "heavy_lane_sources.jsonl", "trace.jsonl", "video_frames.jsonl")}
        sources.update({name + ".mkv": name for name in physical.CAMERAS})
        decoded = {name: {"sha256": name, "decoded_frames": 2} for name in physical.CAMERAS}
        review = {"cameras": {name: {"source_sha256": name, "reviewed_frames": 2,
                     "frames": [{"video_frame": index, "required_markings_visible": True,
                                 "required_bodies_visible": True} for index in range(2)]}
                     for name in physical.CAMERAS}}

        def evaluate(suffix, *, passing=None, turn=None, rows=frames, pixels=review):
            case = prefix + suffix
            measurements = {"heavy_lane_footprint": {"value": {"frames": rows},
                            "sources": sources}}
            if passing is not None:
                measurements["passing_context"] = {"value": passing}
            if turn is not None:
                measurements["turn_preparation_context"] = {"value": turn}
            return physical.evaluate({"case_id": case, "measurements": measurements},
                    {"case_id": case, "source_join_verified": True, "frames": 2,
                     "four_camera_decode": decoded},
                    dict(pixels, case_id=case), trace)

        self.assertEqual(evaluate("unexcused_boundary_crossing")
                         ["physical_checks"]["maneuver"]["status"], "met")
        self.assertEqual(evaluate("within_marked_lane")
                         ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": False})
            ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": True})
            ["physical_checks"]["maneuver"]["status"], "met")
        turn = {"source_frame_count": 2, "turn_plan": {"requested_movement": "turn",
                                                "direction": "right"}}
        self.assertEqual(evaluate("lawful_turn_preparation_boundary_crossing", turn=turn)
                         ["physical_checks"]["maneuver"]["status"], "met")
        missing_review = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        missing_review["cameras"]["approach"]["frames"][0]["required_markings_visible"] = False
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=missing_review)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        incomplete_review = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        incomplete_review["cameras"]["approach"]["frames"] = review["cameras"]["approach"]["frames"][:1]
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=incomplete_review)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        wrong_frame = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        wrong_frame["cameras"]["overview"]["frames"] = [dict(row) for row in review["cameras"]["overview"]["frames"]]
        wrong_frame["cameras"]["overview"]["frames"][1]["video_frame"] = 0
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=wrong_frame)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        bad = [dict(row) for row in frames]
        bad[1]["component_clearances"] = []
        with self.assertRaisesRegex(ValueError, "full heavy-body clearances"):
            evaluate("unexcused_boundary_crossing", rows=bad)

    def test_lifecycle_order_and_early_processing_for_all_selected_cases(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        for suffix in ("within_marked_lane", "unexcused_boundary_crossing",
                       "passing_boundary_crossing",
                       "lawful_turn_preparation_boundary_crossing"):
            case = prefix + suffix
            with self.subTest(case=case, order="early"):
                rejected = lifecycle.run(case, out_of_order=True)
                self.assertEqual(rejected["status"], "rejected")
                self.assertIn("native-exit.json", rejected["reason"])
            with self.subTest(case=case, order="complete"):
                accepted = lifecycle.run(case)
                self.assertEqual(accepted["status"], "passed")
                self.assertEqual(accepted["events"], lifecycle.EVENTS)



if __name__ == "__main__":
    unittest.main()
