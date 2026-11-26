import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from street_scene_construction import construct, load_case


class Adapter:
    def __init__(self, direction, notice):
        self.direction = direction
        self.notice = notice
        self.calls = []
        self.destroyed = []
        self.activity = None

    def configure_street(self, direction, route):
        self.calls.append("configure_street")

    def read_street_direction(self):
        self.calls.append("read_street_direction")
        return self.direction

    def spawn_notice_device(self, device):
        self.calls.append("spawn_notice_device")
        return "notice-fixture"

    def read_notice(self):
        self.calls.append("read_notice")
        return {"state": self.notice, "exact_notice_text": "NO PARKING OR STANDING",
                "erecting_authority_id": "authority-fixture",
                "governing_extent_id": "extent-fixture"}

    def spawn_vehicle(self, position):
        self.calls.append("spawn_vehicle")
        return "vehicle-fixture"

    def drive_to_side(self, vehicle, side, route):
        self.calls.append("drive_to_side")

    def hold_for_activity(self, vehicle, activity):
        self.calls.append("hold_for_activity")
        self.activity = activity

    def read_vehicle_state(self, vehicle):
        self.calls.append("read_vehicle_state")
        return {"activity_request": self.activity}

    def destroy(self, actor):
        self.destroyed.append(actor)


class ConstructionTests(unittest.TestCase):
    def site(self, case):
        digest = "a" * 64
        site = {"assignment_id": case["case_id"].rsplit("__", 1)[0],
                "cell_id": "C412262", "source_kind": "original_reviewed_street_survey",
                "review_status": "reviewed", "street_direction_variant": case["street_direction_request"],
                "notice_variant": case["notice_request"],
                "lane_route_xy_m": [[0, 0], [20, 0]],
                "notice_device": {"blueprint_id": "notice-fixture",
                                  "exact_notice_text": "NO PARKING OR STANDING",
                                  "erecting_authority_id": "authority-fixture",
                                  "governing_extent_id": "extent-fixture"}}
        site.update({name: digest for name in (
            "street_status_sha256", "one_way_order_sha256", "street_boundary_sha256",
            "permitted_direction_sha256", "device_erection_sha256",
            "device_authority_sha256", "device_content_sha256", "device_extent_sha256")})
        return site

    def run_case(self, case, adapter, site=None):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            path = Path(directory) / "site.json"
            path.write_text(json.dumps(site if site is not None else self.site(case)))
            return construct(adapter, path, case["case_id"])

    def test_all_nine_variants_issue_construction_calls(self):
        plan = json.loads((Path(__file__).resolve().parents[1] / "case-plan.json").read_text())
        for case in plan["cases"]:
            with self.subTest(case=case["variant"]):
                self.assertEqual(load_case(case["case_id"]), case)
                adapter = Adapter(case["street_direction_request"], case["notice_request"])
                result = self.run_case(case, adapter)
                self.assertEqual(result["activity_request"], case["activity_request"])
                self.assertIn("drive_to_side", adapter.calls)
                self.assertEqual("spawn_notice_device" in adapter.calls,
                                 case["notice_request"] != "absent")

    def test_missing_reviewed_device_source_rejected(self):
        case = load_case("testing__C412262__NRS-484B-493__motor_vehicle_driver__park_left_notice")
        site = self.site(case)
        del site["device_content_sha256"]
        with self.assertRaisesRegex(ValueError, "device_content_sha256"):
            self.run_case(case, Adapter("one_way", "erected_applicable"), site)

    def test_notice_readback_conflict_rejected(self):
        case = load_case("testing__C412262__NRS-484B-493__motor_vehicle_driver__park_left_notice")
        adapter = Adapter("one_way", "absent")
        with self.assertRaisesRegex(ValueError, "notice erection"):
            self.run_case(case, adapter)
        self.assertEqual(adapter.destroyed, ["notice-fixture"])


if __name__ == "__main__":
    unittest.main()
