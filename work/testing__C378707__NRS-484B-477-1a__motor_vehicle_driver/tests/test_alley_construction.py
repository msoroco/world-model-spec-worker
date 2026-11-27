"""Exercise exact Native construction targets and source gating."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alley_construction", ROOT / "alley_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def site(ordinance=False):
    sources = {name: {"path": "reviewed/" + name + ".json", "sha256": "a" * 64}
               for name in ("map", "alley", "business_frontage", "jurisdiction",
                            "vehicle_blueprint", "passenger_actor", "goods_actor")}
    if ordinance:
        sources["ordinance"] = {"path": "reviewed/ordinance.json", "sha256": "b" * 64}
    return {"alley_kind": "business_district_alley", "public_highway_status": True,
            "business_district_reviewed": True, "jurisdiction_reviewed": True,
            "reviewed_sources": sources,
            "ordinance_status": "reviewed_authorizes_passenger_loading" if ordinance else "reviewed_no_applicable_override",
            "centerline_start_m": [0, 0], "centerline_end_m": [100, 0],
            "loading_station_m": 45, "loading_bay_reviewed": True,
            "passenger_zone_xy_m": [46, 3], "goods_zone_xy_m": [44, -3]}


class ConstructionTests(unittest.TestCase):
    def case(self, variant):
        return module.ASSIGNMENT + "__" + variant

    def test_all_variants_both_directions(self):
        for variant in module.VARIANTS:
            for direction in (-1, 1):
                with self.subTest(variant=variant, direction=direction):
                    plan = module.build_plan(site(variant == "ordinance_passenger_authorized"),
                                             self.case(variant), direction=direction)
                    self.assertEqual(plan["case_id"], self.case(variant))
                    self.assertEqual(plan["target_xy_m"], [45, 0])
                    self.assertEqual(plan["start_xy_m"], [45 - direction * 28, 0])
                    self.assertEqual(plan["depart_xy_m"], [45 + direction * 17, 0])
                    self.assertEqual(plan["capture"]["frames"], 900)
                    self.assertNotEqual(plan["schedule_request_s"], {})
                    self.assertEqual(plan["legal_conclusion"], "unreviewed")

    def test_reviewed_business_district_required(self):
        packet = site()
        packet["business_district_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "business-district"):
            module.build_plan(packet, self.case("passenger_active_stop"))

    def test_reviewed_source_hash_required(self):
        packet = site()
        del packet["reviewed_sources"]["passenger_actor"]["sha256"]
        with self.assertRaisesRegex(ValueError, "passenger_actor"):
            module.build_plan(packet, self.case("passenger_active_stop"))

    def test_oridnance_source_and_status_required(self):
        packet = site()
        with self.assertRaisesRegex(ValueError, "ordinance"):
            module.build_plan(packet, self.case("ordinance_passenger_authorized"))
        packet = site(True)
        packet["ordinance_status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "ordinance"):
            module.build_plan(packet, self.case("ordinance_passenger_authorized"))

    def test_loading_zone_and_station_are_surveyed(self):
        packet = site()
        packet["passenger_zone_xy_m"] = [90, 30]
        with self.assertRaisesRegex(ValueError, "adjacent"):
            module.build_plan(packet, self.case("passenger_active_stop"))
        packet = site()
        packet["loading_station_m"] = 5
        with self.assertRaisesRegex(ValueError, "station"):
            module.build_plan(packet, self.case("passenger_active_stop"))


if __name__ == "__main__":
    unittest.main()
