"""CPU checks for sign, administrative source, route and frame gates."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from signed_road import AID, CASES, SOURCE_ROLES, construct, measure_original, original_site


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def spawn_device(self, xy, blueprint):
        self.calls.append(("spawn", xy, blueprint))
        return "device"

    def set_route(self, device, route):
        self.calls.append(("route", device, route))

    def set_conduct(self, device, conduct, operator):
        self.calls.append(("conduct", device, conduct, operator))

    def set_site(self, device, road, sign):
        self.calls.append(("site", device, road, sign))


class SignedRoadTests(unittest.TestCase):
    def setUp(self):
        root = HERE.parents[1] / ".runtime-work" / "c412927-test-tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def packet(self, case):
        if case.extent == "within":
            start, end = 10, 80
        elif case.extent == "before":
            start, end = 1, 8
        else:
            start, end = 82, 95
        sources = {}
        site = {"format": "reviewed-lvmc-signed-road-v1", "source_kind": "original_reviewed",
                "diagnostic_fixture": False, "case_id": AID + "__" + case.suffix,
                "reviewer": "source review fixture", "municipality": "Las Vegas",
                "map_name": "fixture-map", "map_opendrive_sha256": "0" * 64,
                "roadway_polygon_xy": [[0, 0], [100, 0], [100, 8], [0, 8]],
                "ego_route_xy": ([[start, 4], [end, 4], [end, 6]]
                                 if case.movement == "turn_away" else
                                 [[start, 4], [end, 4]]),
                "longitudinal_station_m": {"route_start": start, "route_end": end},
                "device": {"kind": case.device_kind, "source_verified": True,
                           "blueprint_id": "vehicle.fixture", "device_id": "fixture-device"},
                "operator_conduct": {"kind": case.conduct, "operator_id": "fixture-operator",
                                     "device_id": "fixture-device",
                                     "walker_blueprint_id": "walker.pedestrian.fixture"},
                "restriction_sign": {"in_place": case.sign_state == "posted",
                                     "sign_id": "fixture-sign", "position_xy": [10, 2],
                                     "governed_surface": "roadway",
                                     "categories": ["bicycle", "electric_bicycle", "electric_scooter"],
                                     "station_bounds_m": [20, 80]},
                "administrative_record": {
                    "director_erected_sign": True,
                    "city_traffic_engineer_consulted": True,
                    "metropolitan_police_consulted": True,
                    "director_determined_traffic_flow_impediment": True},
                "legal_verdict": None}
        for role in SOURCE_ROLES:
            value = ("fixture source for " + role + "\n").encode()
            path = self.directory / (role + ".txt")
            path.write_bytes(value)
            digest = sha256(value).hexdigest()
            sources[role] = {"path": path.name, "sha256": digest}
            site[role + "_source_sha256"] = digest
        site["sources"] = sources
        site["restriction_sign"]["source_sha256"] = sources["sign_inventory"]["sha256"]
        path = self.directory / "site.json"
        path.write_text(json.dumps(site) + "\n")
        return path, site

    def test_all_exact_cases_use_reviewed_sources_and_real_adapter_calls(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                path, _ = self.packet(case)
                site = original_site(path, case)
                adapter = FakeAdapter()
                result = construct(adapter, site, case)
                self.assertEqual(result["legal_verdict"], None)
                self.assertEqual([x[0] for x in adapter.calls],
                                 ["spawn", "route", "conduct", "site"])

    def test_rejects_missing_administrative_consultation(self):
        path, site = self.packet(CASES[0])
        site["administrative_record"]["metropolitan_police_consulted"] = False
        path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "both consultations"):
            original_site(path, CASES[0])

    def test_rejects_unreviewed_packet_and_changed_sign_source(self):
        path, site = self.packet(CASES[0])
        site["diagnostic_fixture"] = True
        path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            original_site(path, CASES[0])
        site["diagnostic_fixture"] = False
        path.write_text(json.dumps(site) + "\n")
        (self.directory / "sign_inventory.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source invalid: sign_inventory"):
            original_site(path, CASES[0])

    def test_rejects_wrong_extent_and_discontinuous_original_frames(self):
        path, site = self.packet(CASES[0])
        site["longitudinal_station_m"]["route_start"] = 25
        path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "signed extent"):
            original_site(path, CASES[0])
        _, site = self.packet(CASES[0])
        row = {"original_frame": 10, "time_s": 1.0, "position_xy": [10, 4],
               "device_id": "fixture-device", "operator_id": "fixture-operator",
               "device_source_sha256": site["device_specification_source_sha256"]}
        good = [row, {**row, "original_frame": 11, "time_s": 1.05}]
        self.assertEqual(measure_original(good, site, CASES[0])["frame_count"], 2)
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            measure_original([row, {**row, "original_frame": 12, "time_s": 1.05}],
                             site, CASES[0])


if __name__ == "__main__":
    unittest.main()
