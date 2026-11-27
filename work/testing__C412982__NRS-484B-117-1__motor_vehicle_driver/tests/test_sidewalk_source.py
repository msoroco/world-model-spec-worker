"""CPU checks of source gates, case construction and geometry."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from site_review import ROLES, reviewed_site
from sidewalk_case import BY_SUFFIX, construct
from sidewalk_measure import measure_frame


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def spawn_vehicle(self, position, blueprint):
        self.calls.append(("spawn", position, blueprint))
        return 17

    def set_route(self, ego, route):
        self.calls.append(("route", ego, route))

    def set_target_region(self, ego, sidewalk, entrances, region, kind):
        self.calls.append(("region", ego, sidewalk, entrances, region, kind))

    def enable_controller(self, ego, controller):
        self.calls.append(("controller", ego, controller))


class SidewalkSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c412982-1171-owner" / "test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.case_id = "testing__C412982__NRS-484B-117-1__motor_vehicle_driver__ordinary_sidewalk_travel"
        sources = {}
        for role in ROLES:
            rel = role + ".txt"
            file = self.folder / rel
            file.write_text("reviewed original source for " + role + "\n", encoding="utf-8")
            sources[role] = {"path": rel, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        self.site = {"format": "c412982-reviewed-original-sidewalk-v1",
                     "source_kind": "original_reviewed", "diagnostic_fixture": False,
                     "reviewer": "independent original source reviewer",
                     "case_id": self.case_id, "sources": sources,
                     "map_id": "reviewed-map", "vehicle_blueprint_id": "vehicle.reviewed",
                     "sidewalk_area_id": "walk-1", "pedestrian_purpose": True,
                     "sidewalk_area_polygon_xy": [[0, 0], [10, 0], [10, 3], [0, 3]],
                     "entrance_polygons_xy": {
                         "permanent_driveway": [[2, 0], [3, 0], [3, 3], [2, 3]],
                         "temporary_driveway": [[4, 0], [5, 0], [5, 3], [4, 3]],
                         "alley_entrance": [[6, 0], [7, 0], [7, 3], [6, 3]]},
                     "approach_route_xy": [[-2, 1], [1, 1], [8, 1]],
                     "requested_travel_region": "sidewalk", "requested_entrance_kind": None,
                     "vehicle_design": {"power": "combustion", "wheel_count": 4,
                                        "designed_for_wheel_count": 4},
                     "operator_context": {"role": "ordinary", "identity": "driver-1",
                                          "duty_period": "episode"}}
        for role in ROLES:
            self.site[role + "_source_sha256"] = sources[role]["sha256"]
        self.site["body_geometry_source_sha256"] = sources["vehicle_blueprint_and_power"]["sha256"]
        self.path = self.folder / "site.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.site, indent=2) + "\n", encoding="utf-8")

    def test_original_site_and_four_real_calls(self):
        site = reviewed_site(self.path, self.case_id)
        adapter = FakeAdapter()
        result = construct(adapter, site, BY_SUFFIX["ordinary_sidewalk_travel"])
        self.assertEqual(result["ego"], 17)
        self.assertEqual([call[0] for call in adapter.calls],
                         ["spawn", "route", "region", "controller"])

    def test_hash_or_original_flag_rejected(self):
        self.site["sources"]["property_line"]["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "original source invalid"):
            reviewed_site(self.path, self.case_id)
        self.site["sources"]["property_line"]["sha256"] = hashlib.sha256(
            (self.folder / "property_line.txt").read_bytes()).hexdigest()
        self.site["diagnostic_fixture"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "original sidewalk packet identity"):
            reviewed_site(self.path, self.case_id)

    def test_electric_exception_needs_vehicle_and_duty_sources(self):
        site = reviewed_site(self.path, self.case_id)
        with self.assertRaisesRegex(ValueError, "vehicle design differs"):
            construct(FakeAdapter(), site, BY_SUFFIX["electric_three_wheel_law_officer"])
        site["vehicle_design"] = {"power": "solely_electric", "wheel_count": 3,
                                  "designed_for_wheel_count": 3}
        site["operator_context"] = {"role": "law_officer", "identity": "officer-1",
                                    "duty_period": "episode", "authorized": True}
        with self.assertRaisesRegex(ValueError, "official duty missing"):
            construct(FakeAdapter(), site, BY_SUFFIX["electric_three_wheel_law_officer"])
        site["operator_context"]["on_official_duty"] = True
        self.assertEqual(construct(FakeAdapter(), site,
                                   BY_SUFFIX["electric_three_wheel_law_officer"])["ego"], 17)

    def test_physical_areas_keep_entrance_separate(self):
        row = {"original_frame": 91, "time_s": 4.55, "vehicle_actor_id": 17,
               "body_polygon_xy": [[2.2, .5], [2.8, .5], [2.8, 1.5], [2.2, 1.5]],
               "body_geometry_source_sha256": self.site["body_geometry_source_sha256"]}
        result = measure_frame(row, self.site)
        self.assertGreater(result["sidewalk_overlap_area_m2"], 0)
        self.assertGreater(result["entrance_overlap_area_m2"]["permanent_driveway"], 0)
        self.assertEqual(result["entrance_overlap_area_m2"]["alley_entrance"], 0)
        row["body_geometry_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "body source differs"):
            measure_frame(row, self.site)


if __name__ == "__main__":
    unittest.main()
