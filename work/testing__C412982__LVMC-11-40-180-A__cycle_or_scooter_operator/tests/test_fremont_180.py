"""Focused CPU tests of original source gates and physical branch geometry."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fremont_180 import AID, BY_SUFFIX, DEVICE_KINDS, SOURCE_ROLES
from fremont_180 import construct, measure_original, original_site


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def spawn_device(self, position, blueprint):
        self.calls.append(("spawn", position, blueprint))
        return 15

    def set_route(self, device, route):
        self.calls.append(("route", device, route))

    def set_conduct(self, device, conduct, operator):
        self.calls.append(("conduct", device, conduct, operator))

    def set_site(self, device, sidewalks, road, signs):
        self.calls.append(("site", device, sidewalks, road, signs))


class FremontSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c412982-lvmc180-owner" / "test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.case = BY_SUFFIX["bicycle_riding_north"]
        self.sources = {}
        for role in SOURCE_ROLES:
            path = self.folder / (role + ".txt")
            path.write_text("reviewed original " + role + "\n", encoding="utf-8")
            self.sources[role] = {"path": path.name,
                                  "sha256": sha256(path.read_bytes()).hexdigest()}
        self.site = {
            "format": "reviewed-fremont-sidewalk-v1", "source_kind": "original_reviewed",
            "diagnostic_fixture": False, "reviewer": "independent original site reviewer",
            "case_id": AID + "__" + self.case.suffix, "sources": self.sources,
            "municipality": "Las Vegas", "street": "Fremont Street",
            "from_cross_street": "Main Street", "to_cross_street": "Seventh Street",
            "map_name": "reviewed-map", "map_opendrive_sha256": "a" * 64,
            "sidewalk_pedestrian_purpose": True,
            "sidewalk_polygons_xy": {
                "north": [[0, 0], [30, 0], [30, 3], [0, 3]],
                "south": [[0, 9], [30, 9], [30, 12], [0, 12]],
            },
            "road_polygon_xy": [[0, 3], [30, 3], [30, 9], [0, 9]],
            "ego_route_xy": [[6, 1], [12, 1]],
            "longitudinal_station_m": {"main": 0, "seventh": 30,
                                        "route_start": 6, "route_end": 12},
            "device": {"kind": "bicycle", "source_verified": True,
                       "blueprint_id": "vehicle.reviewed_bicycle", "device_id": "bike-1"},
            "operator_conduct": {"kind": "riding", "operator_id": "rider-1",
                                 "device_id": "bike-1"},
            "sign_inventory": [{"sign_id": "sign-1", "position_xy": [4, 2],
                                "original_content_source_sha256":
                                    self.sources["sign_inventory"]["sha256"],
                                "categories": list(DEVICE_KINDS)}],
            "sign_coverage_judgment": None, "legal_verdict": None,
        }
        for role in SOURCE_ROLES:
            self.site[role + "_source_sha256"] = self.sources[role]["sha256"]
        self.path = self.folder / "site.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.site) + "\n", encoding="utf-8")

    def test_original_review_and_adapter_calls(self):
        site = original_site(self.path, self.case)
        adapter = FakeAdapter()
        answer = construct(adapter, site, self.case)
        self.assertEqual(answer["device"], 15)
        self.assertEqual([x[0] for x in adapter.calls],
                         ["spawn", "route", "conduct", "site"])

    def test_diagnostic_and_wrong_source_rejected(self):
        self.site["diagnostic_fixture"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "reviewed original Fremont"):
            original_site(self.path, self.case)
        self.site["diagnostic_fixture"] = False
        self.site["sources"]["main_street_intersection"]["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "original source invalid"):
            original_site(self.path, self.case)

    def test_geographic_and_conduct_branches_are_real(self):
        self.site["street"] = "Other Street"
        self.save()
        with self.assertRaisesRegex(ValueError, "Fremont Main-to-Seventh"):
            original_site(self.path, self.case)
        self.site["street"] = "Fremont Street"
        self.site["ego_route_xy"] = [[6, 5], [12, 5]]
        self.save()
        with self.assertRaisesRegex(ValueError, "selected surface"):
            original_site(self.path, self.case)
        self.site["ego_route_xy"] = [[6, 1], [12, 1]]
        self.site["operator_conduct"]["kind"] = "walking"
        self.save()
        with self.assertRaisesRegex(ValueError, "riding versus walking"):
            original_site(self.path, self.case)

    def test_sign_source_and_three_categories_are_required(self):
        self.site["sign_inventory"][0]["categories"] = ["bicycle"]
        self.save()
        with self.assertRaisesRegex(ValueError, "three covered categories"):
            original_site(self.path, self.case)

    def test_original_frames_and_measurements(self):
        site = original_site(self.path, self.case)
        rows = [{"original_frame": 100 + index, "time_s": 10 + index / 20,
                 "position_xy": [6 + index, 1], "device_id": "bike-1",
                 "operator_id": "rider-1",
                 "device_source_sha256": site["device_specification_source_sha256"]}
                for index in range(3)]
        measured = measure_original(rows, site, self.case)
        self.assertEqual(measured["sidewalk_center_frames"], 3)
        self.assertIsNone(measured["legal_judgment"])
        rows[1]["device_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "device or conduct source"):
            measure_original(rows, site, self.case)


if __name__ == "__main__":
    unittest.main()
