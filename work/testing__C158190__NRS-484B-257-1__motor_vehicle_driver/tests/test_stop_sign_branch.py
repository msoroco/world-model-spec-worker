"""CPU tests for source-bound C158190 stop-sign candidate construction."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c158190_stop_sign_branch", ROOT / "stop_sign_branch.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Adapter:
    def __init__(self):
        self.control = "stop_sign"
        self.markings = {"stop_line_present": False, "near_crosswalk_present": False,
                         "sidewalk_derived_crosswalk_present": False}
        self.stations = [{"view_of_through_traffic": False}, {"view_of_through_traffic": True}]
        self.calls = []

    def read_control(self, approach):
        self.calls.append(("control", approach))
        return self.control

    def survey_markings(self, approach):
        self.calls.append(("markings", approach))
        return self.markings

    def survey_view_stations(self, approach):
        self.calls.append(("view", approach))
        return self.stations

    def spawn_through_vehicle(self, route, delay):
        self.calls.append(("spawn", route["route_source_id"], delay))
        return "native-through-1"


class StopSignBranchTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="c158190-stop-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.case = MODULE.ASSIGNMENT + "__stop_nearest_view_response"
        self.site = {
            "assignment_id": MODULE.ASSIGNMENT,
            "cell_id": "C158190",
            "control": "stop_sign",
            "source_kind": "original_site_survey",
            "review_status": "reviewed",
            "police_control_active": False,
            "traffic_signal_control_active": False,
            "stop_line_present": False,
            "near_crosswalk_present": False,
            "sidewalk_derived_crosswalk_present": False,
            "stop_sign": {"governed_approach_id": "one-way-ego"},
            "approach_view_stations": [
                {"station_id": "far", "distance_to_intersection_m": 12.0, "reviewed_visible": False},
                {"station_id": "near", "distance_to_intersection_m": 3.0, "reviewed_visible": True},
            ],
            "through_vehicle": {"route_source_id": "through-east"},
            "case_plans": {self.case: {"ego_response": "stop_then_yield", "through_start_delay_s": 2.0}},
            "source_records": {},
        }
        for index, key in enumerate(MODULE.SOURCES):
            name = "source-" + str(index) + ".txt"
            data = (key + ": reviewed source test bytes\n").encode()
            (self.directory / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.site[key] = digest
            self.site["source_records"][key] = {"path": name, "sha256": digest}
        self.path = self.directory / "site.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.site, sort_keys=True) + "\n")

    def test_exact_stop_governance_and_approach(self):
        adapter = Adapter()
        receipt = MODULE.construct(adapter, self.path, self.case)
        self.assertEqual(receipt["control"], "stop_sign")
        self.assertEqual(receipt["cell_id"], "C158190")
        self.assertEqual([call[0] for call in adapter.calls], ["control", "markings", "view", "spawn"])
        self.assertEqual(adapter.calls[0][1], "one-way-ego")
        self.assertEqual(adapter.calls[-1], ("spawn", "through-east", 2.0))

    def test_second_controlled_response_uses_same_fixed_site(self):
        second = MODULE.ASSIGNMENT + "__stop_nearest_view_uninterrupted"
        self.site["case_plans"][second] = {"ego_response": "stop_then_cross", "through_start_delay_s": 9.0}
        self.save()
        adapter = Adapter()
        receipt = MODULE.construct(adapter, self.path, second)
        self.assertEqual(receipt["planned_response"], "stop_then_cross")
        self.assertEqual(adapter.calls[-1], ("spawn", "through-east", 9.0))

    def test_yield_relabel_rejected_before_native_calls(self):
        self.site["control"] = "yield_sign"
        self.save()
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, "fixed C158190 stop-sign identity"):
            MODULE.construct(adapter, self.path, self.case)
        self.assertEqual(adapter.calls, [])

    def test_source_byte_tamper_rejected(self):
        (self.directory / "source-3.txt").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "original source bytes differ"):
            MODULE.validate_site(self.path, self.case)

    def test_unreviewed_survey_rejected(self):
        self.site["review_status"] = "diagnostic"
        self.save()
        with self.assertRaisesRegex(ValueError, "independently reviewed original"):
            MODULE.validate_site(self.path, self.case)

    def test_active_signal_exclusion_rejected(self):
        self.site["traffic_signal_control_active"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "officer and signal exclusions"):
            MODULE.validate_site(self.path, self.case)

    def test_native_yield_control_rejected(self):
        adapter = Adapter()
        adapter.control = "yield_sign"
        with self.assertRaisesRegex(ValueError, "Native stop-sign governance"):
            MODULE.construct(adapter, self.path, self.case)
        self.assertEqual([call[0] for call in adapter.calls], ["control"])

    def test_marking_and_view_readbacks_rejected(self):
        adapter = Adapter()
        adapter.markings["near_crosswalk_present"] = True
        with self.assertRaisesRegex(ValueError, "Native markings contradict"):
            MODULE.construct(adapter, self.path, self.case)
        adapter = Adapter()
        adapter.stations = [{"view_of_through_traffic": False}] * 2
        with self.assertRaisesRegex(ValueError, "Native through-highway view"):
            MODULE.construct(adapter, self.path, self.case)


if __name__ == "__main__":
    unittest.main()
