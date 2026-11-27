import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("parked_construction", ROOT / "parked_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ParkedConstructionTests(unittest.TestCase):
    def packet(self, variant):
        sources = {name: {"path": name + ".txt", "sha256": "a" * 64} for name in
                   ("map", "highway_boundary", "dedication", "public_use",
                    "parking_permission", "vehicle_blueprint", "approach_route")}
        return {
            "case_id": module.ASSIGNMENT + "__" + variant,
            "source_kind": "reviewed_original_native_site",
            "public_highway_status": True,
            "public_dedication_reviewed": True,
            "public_vehicular_use_reviewed": True,
            "parking_permitted_at_capture_time": True,
            "reviewed_sources": sources,
            "highway_polygon_xy_m": [[-100, -10], [100, -10], [100, 10], [-100, 10]],
            "parking_bay_polygon_xy_m": [[-15, -9], [5, -9], [5, -3], [-15, -3]],
            "parked_vehicle_center_xy_m": [-8, -6],
            "ego_departure_entry_xy_m": [0, -2],
            "ego_departure_exit_xy_m": [30, -2],
            "parked_vehicle_center_fallback_xy_m": [-4, -6],
            "ego_departure_entry_fallback_xy_m": [4, -2],
            "ego_departure_exit_fallback_xy_m": [34, -2],
            "rear_approach_route_xy_m": [[-70, -2], [60, -2]],
            "opposing_approach_route_xy_m": [[70, 2], [-70, 2]],
            "nonconflicting_opposing_route_reviewed": True,
        }

    def test_all_variants_have_actual_geometry_and_controller_requests(self):
        for variant in module.VARIANTS:
            packet = self.packet(variant)
            built = module.build_plan(packet, packet["case_id"])
            self.assertEqual(len(built["ego_departure_route_xy_m"]), 3)
            self.assertGreater(len(built["other_approach_route_xy_m"]), 1)
            self.assertIn(built["other_approach_kind"], ("rear", "opposing"))
            self.assertEqual(built["capture"]["frames"], 900)
            alternate = module.build_plan(packet, packet["case_id"], direction=-1)
            self.assertNotEqual(built["ego_departure_route_xy_m"],
                                alternate["ego_departure_route_xy_m"])

    def test_rejects_missing_public_or_parking_basis(self):
        for key in ("public_highway_status", "public_dedication_reviewed",
                    "public_vehicular_use_reviewed", "parking_permitted_at_capture_time"):
            packet = self.packet("rear_wait")
            packet[key] = False
            with self.assertRaisesRegex(ValueError, "source review missing"):
                module.build_plan(packet, packet["case_id"])

    def test_rejects_wrong_bay_and_missing_other_route(self):
        packet = self.packet("rear_wait")
        packet["parked_vehicle_center_xy_m"] = [15, -6]
        with self.assertRaisesRegex(ValueError, "outside reviewed permitted bay"):
            module.build_plan(packet, packet["case_id"])
        packet = self.packet("opposing_wait")
        packet.pop("opposing_approach_route_xy_m")
        with self.assertRaisesRegex(ValueError, "route missing"):
            module.build_plan(packet, packet["case_id"])


if __name__ == "__main__":
    unittest.main()
