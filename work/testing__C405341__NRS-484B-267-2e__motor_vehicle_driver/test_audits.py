"""Independent audit negative gates and original frame joins."""
import tempfile
from pathlib import Path
import unittest
from comparison_audit import audit_comparison
from delivery_audit import audit_attempt, audit_pixels
from emergency_construction import CASES
from native_packet import AID


class AuditTests(unittest.TestCase):
    def test_missing_original_is_rejected(self):
        scratch = Path(__file__).resolve().parents[2] / ".runtime-work/c405341-2e/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            case_id = AID + "__" + CASES[0].suffix
            with self.assertRaisesRegex(ValueError, "original attempt missing"):
                audit_attempt(root / "missing", root / "result.json", case_id)

    def test_lane_join_and_pixel_review_are_required(self):
        history = [{"frame": i, "native_frame": 100+i, "movement_visible": False,
                    "driver_hand_signal_visible": False, "ego_lane_id": "lane-1"} for i in range(900)]
        cues = [{"frame": i, "native_frame": 100+i, "camera": "driver_reference",
                 "pixel_review_source": "original-roi", "reviewer": "independent",
                 "roi_pixels": [1, 2, 3, 4], "frame_md5": "0"*32,
                 "movement_visible": False, "hand_signal_visible": False,
                 "ego_lane_id": "lane-1"} for i in range(900)]
        digests = ["0"*32]*900
        self.assertEqual(len(audit_pixels(cues, history, CASES[0], digests)["ego_lane_original_frames"]), 900)
        cues[340]["native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame join"):
            audit_pixels(cues, history, CASES[0], digests)

    def test_comparison_requires_exact_original_audits(self):
        with self.assertRaisesRegex(ValueError, "comparison must include every exact case"):
            audit_comparison("available_lane_choice", {})


if __name__ == "__main__":
    unittest.main()

class ComparisonPositiveTests(unittest.TestCase):
    def test_all_ten_source_bound_comparisons(self):
        import json
        plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
        by_name = {case.suffix: case for case in CASES}
        scratch = Path(__file__).resolve().parents[2] / ".runtime-work/c405341-2e/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            folder = Path(directory)
            for row in plan["comparisons"]:
                paths = {}
                for case_id in row["case_ids"]:
                    case = by_name[case_id.removeprefix(AID + "__")]
                    context = {key: "same-source" for key in (
                        "road_source_sha256", "weather_sha256", "traffic_sha256",
                        "ego_route_sha256", "camera_plan_sha256", "unit_route_sha256",
                        "lane_graph_sha256")}
                    if case.condition == "traffic_unsafe":
                        context["traffic_sha256"] = "occupied-traffic-source"
                    if case.condition == "roadway_impossible":
                        context["road_source_sha256"] = "no-third-lane-source"
                        context["lane_graph_sha256"] = "no-third-lane-source"
                        context["ego_route_sha256"] = "adjacent-only-route-source"
                    if case.condition == "weather_unsafe":
                        context["weather_sha256"] = "wet-weather-source"
                    if not case.approaching:
                        context["ego_route_sha256"] = "departing-ego-source"
                    if case.motion_state != "moving":
                        context["unit_route_sha256"] = case.motion_state + "-source"
                    item = {
                        "format": "c405341-2e-original-delivery-audit-v1",
                        "case_id": case_id, "original_frame_count": 900,
                        "legal_status": "unresolved",
                        "source_sha256": {"capture-seal.json": "original-seal-hash"},
                        "scene_context": context,
                        "authority": {"class": case.unit_class, "equipment_source": "same-equipment"},
                        "lane_site": {"nonadjacent_route_connected": case.condition != "roadway_impossible"},
                        "lane_pixel_audit": {"ego_lane_original_frames":
                            ["lane-2"]*900 if case.lane_choice == "nonadjacent" else ["lane-1"]*900,
                            "movement_visible_frames": 20 if case.motion_state == "preparing_movement" else 0,
                            "hand_signal_visible_frames": 20 if case.motion_state == "preparing_hand_signal" else 0},
                        "original_condition_counts": {
                            "flashing_frames": 450 if case.qualifying_lights else 0,
                            "approaching_frames": 900 if case.approaching else 0,
                            "traffic_occupied_frames": 200 if case.condition == "traffic_unsafe" else 0,
                            "weather_adverse_frames": 900 if case.condition == "weather_unsafe" else 0,
                            "other_hazard_frames": 200 if case.condition == "other_hazard" else 0,
                            "officer_direction_frames": 100 if case.officer_direction else 0},
                    }
                    path = folder / (case.suffix + ".json")
                    path.write_text(json.dumps(item) + "\n")
                    paths[case_id] = path
                with self.subTest(comparison=row["comparison_id"]):
                    proof = audit_comparison(row["comparison_id"], paths)
                    self.assertEqual(proof["case_ids"], row["case_ids"])
