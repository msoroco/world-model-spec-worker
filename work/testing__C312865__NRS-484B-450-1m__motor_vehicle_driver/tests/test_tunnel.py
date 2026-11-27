import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tunnel import CASES, construct, inside_polygon, measure_original, validate_site


def site():
    source = "a" * 64
    return {"cell_id": "C312865", "layout": "tunnel",
            "highway_status": "source_reviewed_public_vehicular_use",
            "map_source_sha256": source, "highway_source_sha256": source,
            "tunnel_source_sha256": source, "portal_source_sha256": source,
            "route_source_sha256": source, "ego_blueprint_source_sha256": source,
            "other_blueprint_source_sha256": source,
            "tunnel_polygon_xy": [[0, -5], [100, -5], [100, 5], [0, 5]],
            "ego_approach_xy": [-30, 0], "outside_target_xy": [-10, 0],
            "inside_target_xy": [50, 0], "other_vehicle_xy": [70, 2],
            "approach_route_xy": [[-30, 0], [-10, 0], [50, 0]],
            "other_vehicle_route_xy": [[70, 2], [80, 2]]}


class Adapter:
    def __init__(self):
        self.owned = []
        self.destroyed = []
        self.fail_route = False

    def spawn_vehicle(self, point, role):
        self.owned.append(role)
        return role

    def configure_other_vehicle(self, actor, exception, route):
        assert actor == "other_vehicle"

    def set_route(self, actor, route, target_xy):
        if self.fail_route:
            raise ValueError("route rejected")

    def request_halt(self, actor, target_xy, activity):
        assert activity in ("stop", "stand", "park")

    def destroy(self, actor):
        self.destroyed.append(actor)


class TunnelTests(unittest.TestCase):
    def test_portals_isolate_destinations_and_full_body(self):
        setting = site()
        validate_site(setting)
        self.assertFalse(inside_polygon([-10, 0], setting["tunnel_polygon_xy"]))
        self.assertTrue(inside_polygon([0, 0], setting["tunnel_polygon_xy"]))
        self.assertTrue(inside_polygon([50, 0], setting["tunnel_polygon_xy"]))
        for case in CASES:
            built = construct(Adapter(), setting, case)
            self.assertEqual(built["requested_endpoint_xy"],
                             setting["outside_target_xy"] if case.endpoint.startswith("outside")
                             else setting["inside_target_xy"])
            self.assertIsNone(built["legal_judgment"])
        altered = copy.deepcopy(setting)
        altered["inside_target_xy"] = [120, 0]
        with self.assertRaisesRegex(ValueError, "do not isolate"):
            validate_site(altered)

    def test_missing_highway_and_cleanup_rejected(self):
        altered = site()
        altered["highway_status"] = "assumed"
        with self.assertRaisesRegex(ValueError, "highway dedication"):
            validate_site(altered)
        adapter = Adapter()
        adapter.fail_route = True
        with self.assertRaisesRegex(ValueError, "route rejected"):
            construct(adapter, site(), CASES[1])
        self.assertEqual(adapter.destroyed, ["ego", "other_vehicle"])

    def test_original_body_and_activity_are_separate_from_legal_judgment(self):
        setting = site()
        vertices = [[49, -1], [51, -1], [51, 1], [49, 1]]
        rows = [{"original_frame": i + 100, "time_s": 3 + i / 20,
                 "source_sha256": "b" * 64, "ego_control_source_sha256": "c" * 64,
                 "map_source_sha256": setting["map_source_sha256"],
                 "highway_source_sha256": setting["highway_source_sha256"],
                 "tunnel_source_sha256": setting["tunnel_source_sha256"],
                 "portal_source_sha256": setting["portal_source_sha256"],
                 "ego_id": "ego", "other_vehicle_id": "other",
                 "ego_body_vertices_xy": vertices, "ego_speed_mps": 0,
                 "other_vehicle_speed_mps": 0,
                 "other_vehicle_purpose": "unknown", "activity_readback": "stand"}
                for i in range(900)]
        report = measure_original(rows, setting, CASES[2])
        self.assertTrue(report["terminal_body_inside_tunnel"])
        self.assertEqual(report["observed_activity"], "stand")
        self.assertEqual(report["legal_judgment"], "unresolved")
        rows[-1]["ego_body_vertices_xy"] = [[99, -1], [101, -1], [101, 1], [99, 1]]
        report = measure_original(rows, setting, CASES[2])
        self.assertFalse(report["terminal_body_inside_tunnel"])
        rows[-1]["portal_source_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "site source changed"):
            measure_original(rows, setting, CASES[2])


if __name__ == "__main__":
    unittest.main()
