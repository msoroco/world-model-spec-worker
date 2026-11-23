import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_turn_check import check
from stand_route import CASES, inspect, make
from candidate_opendrive import build as build_xodr, inspect as inspect_xodr
from candidate_comparison_audit import audit
from xml.etree import ElementTree as ET


class StandRouteTest(unittest.TestCase):
    def test_both_candidate_routes_are_connected_and_differ_only_in_stand_distance(self):
        near, far = make("near_stand"), make("far_stand")
        inspect(near)
        inspect(far)
        self.assertEqual(near["road_lanes"], far["road_lanes"])
        self.assertEqual(near["directed_edges"], far["directed_edges"])
        self.assertEqual(near["intended_route"], far["intended_route"])
        self.assertLess(far["departure"]["point"][0], near["departure"]["point"][0])

    def test_disconnected_route_is_rejected(self):
        route = make("near_stand")
        route["road_lanes"][2]["start"][0] += 1
        with self.assertRaisesRegex(ValueError, "disconnected"):
            inspect(route)

    def test_notice_after_intersection_is_rejected(self):
        route = make("near_stand")
        route["posted_notice"]["point"][0] = 0
        with self.assertRaisesRegex(ValueError, "order differs"):
            inspect(route)

    def test_both_opendrive_routes_have_continuous_driving_lanes(self):
        for case in CASES:
            with self.subTest(case=case):
                proof = inspect_xodr(build_xodr(case), case)
                self.assertEqual(proof["routes"][0], [10, 110, 11])

    def test_opendrive_displaced_exit_is_rejected(self):
        root = ET.fromstring(build_xodr("near_stand"))
        geometry = root.find("./road[@id='11']/planView/geometry")
        geometry.set("x", "1")
        with self.assertRaisesRegex(ValueError, "authored road geometry differs"):
            inspect_xodr(ET.tostring(root), "near_stand")

    def test_opendrive_missing_right_arc_is_rejected(self):
        root = ET.fromstring(build_xodr("near_stand"))
        geometry = root.find("./road[@id='110']/planView/geometry")
        geometry.remove(geometry.find("arc"))
        ET.SubElement(geometry, "line")
        with self.assertRaisesRegex(ValueError, "endpoint discontinuity|right turn arc absent"):
            inspect_xodr(ET.tostring(root), "near_stand")

    def test_opendrive_widened_lane_is_rejected(self):
        root = ET.fromstring(build_xodr("near_stand"))
        width = root.find("./road[@id='10']/lanes/laneSection/right/lane/width")
        width.set("a", "4.0")
        with self.assertRaisesRegex(ValueError, "lane width"):
            inspect_xodr(ET.tostring(root), "near_stand")

    def test_opendrive_counterflow_lane_is_rejected(self):
        root = ET.fromstring(build_xodr("near_stand"))
        section = root.find("./road[@id='10']/lanes/laneSection")
        left = ET.SubElement(section, "left")
        ET.SubElement(left, "lane", {"id": "1", "type": "driving"})
        with self.assertRaisesRegex(ValueError, "counterflow"):
            inspect_xodr(ET.tostring(root), "near_stand")

    def test_opendrive_wrong_turn_notice_is_rejected(self):
        root = ET.fromstring(build_xodr("near_stand"))
        root.find("./road[@id='10']/signals/signal").set("subtype", "left")
        with self.assertRaisesRegex(ValueError, "notice object"):
            inspect_xodr(ET.tostring(root), "near_stand")

    def test_comparison_audit_accepts_only_distance_change(self):
        result = audit(make("near_stand"), make("far_stand"),
                       build_xodr("near_stand"), build_xodr("far_stand"))
        self.assertEqual(result["difference_m"], 20)

    def test_comparison_audit_rejects_changed_notice_meaning(self):
        far = make("far_stand")
        far["posted_notice"]["meaning"] = "left turn"
        with self.assertRaisesRegex(ValueError, "notice context"):
            audit(make("near_stand"), far, build_xodr("near_stand"), build_xodr("far_stand"))

    def test_comparison_audit_rejects_changed_crossing_map(self):
        root = ET.fromstring(build_xodr("far_stand"))
        root.find("./road[@id='20']").set("name", "altered roadway")
        with self.assertRaisesRegex(ValueError, "maps changed"):
            audit(make("near_stand"), make("far_stand"),
                  build_xodr("near_stand"), ET.tostring(root))


class SavedTurnTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        evidence = self.root / "fixture-source.txt"
        evidence.write_text("synthetic CPU fixture; never original evidence\n")
        ref = {"path": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
        self.trace = {
            "case": "near_stand",
            "context": {key: {"status": "documented", "source": ref}
                        for key in ("cab_license", "stand_designation", "posted_notice", "jurisdiction")},
            "events": [
                {"kind": "stand_departure", "time_s": 1, "source": ref},
                {"kind": "lane_entry", "time_s": 2, "source": ref},
                {"kind": "intersection_entry", "intersection_id": "first", "time_s": 5, "source": ref},
                {"kind": "intersection_exit", "intersection_id": "first", "time_s": 7,
                 "approach_heading_deg": 0, "departure_heading_deg": -90,
                 "exit_lane": "south_exit", "source": ref},
            ],
        }

    def test_right_turn_measurement(self):
        result = check(self.trace, make("near_stand"), self.root)
        self.assertTrue(result["right_turn_observed"])
        self.assertEqual(result["turn_angle_deg"], -90)

    def test_straight_exit_is_measured_not_accepted_as_right_turn(self):
        event = self.trace["events"][-1]
        event["departure_heading_deg"] = 0
        event["exit_lane"] = "east_exit"
        result = check(self.trace, make("near_stand"), self.root)
        self.assertFalse(result["right_turn_observed"])

    def test_missing_documentary_context_is_rejected(self):
        del self.trace["context"]["stand_designation"]
        with self.assertRaisesRegex(ValueError, "stand_designation"):
            check(self.trace, make("near_stand"), self.root)

    def test_stale_source_hash_is_rejected(self):
        self.trace["events"][0]["source"] = {"path": "fixture-source.txt", "sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "hash differs"):
            check(self.trace, make("near_stand"), self.root)

    def test_second_intersection_first_is_rejected(self):
        self.trace["events"][2]["intersection_id"] = "second"
        with self.assertRaisesRegex(ValueError, "misordered"):
            check(self.trace, make("near_stand"), self.root)


if __name__ == "__main__":
    unittest.main()
