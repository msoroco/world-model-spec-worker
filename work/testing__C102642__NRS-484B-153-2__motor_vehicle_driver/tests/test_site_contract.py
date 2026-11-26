import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("site_contract", ROOT / "site_contract.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


def packet():
    return {"source_kind": "original_map_survey", "map_sha256": "map-hash",
            "map_name": "surveyed-map", "lane_id": "loading-lane",
            "loading_site_id": "crest-loading", "governing_zone_source": "original-zone-inventory",
            "loading_zone_status": "permitted_for_authored_loading",
            "parked_vehicle_blueprint": "vehicle.a", "passing_vehicle_blueprint": "vehicle.b",
            "driver_actor_id": "driver", "route_grade_samples": [[0, 0], [10, 1], [20, 0]],
            "loading_station_m": 12, "loading_xy": [12, 2.5],
            "road_edge_xy": [[0, 2], [20, 2]],
            "maximum_loading_edge_offset_m": 1,
            "parked_heading_xy": [1, 0], "parked_center_xy": [12, 2.5],
            "passing_route_xy": [[8, 4], [16, 4]]}


class SiteContractTests(unittest.TestCase):
    def test_five_case_actions_and_both_traffic_sides(self):
        source = packet()
        for key, (act, relation, variant) in site.CASE_ACTIONS.items():
            if key.startswith("door_interference_physical_range-"):
                continue
            with self.subTest(key=key):
                result = site.validate_site(source, key)
                self.assertEqual(result["selected_act"], act)
                self.assertEqual(result["clearance_variant"], variant)
                self.assertEqual(result["selected_door_side"],
                                 "left" if relation == "near" else "right")
                self.assertEqual(result["crest_measurement"]["loading_to_crest_m"], 2)
        source["passing_route_xy"] = [[8, 1], [16, 1]]
        self.assertEqual(site.validate_site(source, "open_near_overlap")["selected_door_side"],
                         "right")

    def test_engineering_clearance_requires_reviewed_route_feasibility(self):
        source = packet()
        key = "door_interference_physical_range-0000"
        with self.assertRaisesRegex(ValueError, "reviewed passing clearance route source"):
            site.validate_site(source, key)
        source["passing_clearance_route_source"] = {"path": "route.json", "sha256": "1" * 64}
        source["passing_clearance_feasible_range_m"] = [0.2, 1.3]
        self.assertEqual(site.validate_site(source, key)["requested_engineering_clearance_m"], .25)
        source["passing_clearance_feasible_range_m"] = [0.5, 1.3]
        with self.assertRaisesRegex(ValueError, "outside reviewed route feasibility"):
            site.validate_site(source, key)

    def test_missing_governance_or_grade_fails(self):
        source = packet()
        source["governing_zone_source"] = ""
        with self.assertRaises(ValueError):
            site.validate_site(source, "board_near")
        source = packet()
        source["route_grade_samples"] = [[0, 0], [10, 0], [20, 1]]
        with self.assertRaises(ValueError):
            site.validate_site(source, "board_near")
        source = packet()
        source["loading_xy"] = [12, 20]
        with self.assertRaises(ValueError):
            site.validate_site(source, "board_near")

    def test_survey_hash_and_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            data = json.dumps(packet()).encode()
            path.write_bytes(data)
            self.assertEqual(site.read_packet(path, hashlib.sha256(data).hexdigest())["map_name"],
                             "surveyed-map")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                site.read_packet(path, "0" * 64)
            path.write_text(json.dumps({**packet(), "source_kind": "synthetic"}))
            with self.assertRaises(ValueError):
                site.read_packet(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_original_passing_route_hash_is_checked_before_site_use(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            route = base / "route.json"
            route.write_text(json.dumps({"source_kind": "original_surveyed_passing_route",
                                         "route_xy": [[8, 4], [16, 4]]}))
            source = packet()
            source["passing_clearance_route_source"] = {
                "path": route.name, "sha256": hashlib.sha256(route.read_bytes()).hexdigest()}
            source["passing_clearance_feasible_range_m"] = [0.2, 1.3]
            survey = base / "survey.json"
            survey.write_text(json.dumps(source))
            digest = hashlib.sha256(survey.read_bytes()).hexdigest()
            site.validate_site(site.read_packet(survey, digest),
                               "door_interference_physical_range-0001")
            route.write_text("{}")
            with self.assertRaisesRegex(ValueError, "route source hash mismatch"):
                site.read_packet(survey, digest)


if __name__ == "__main__":
    unittest.main()
