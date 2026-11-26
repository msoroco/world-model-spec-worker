import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from package_spec import AID
from right_turn import construct


class SourceGateTests(unittest.TestCase):
    def site(self, suffix="right_turn_purpose"):
        purpose = {"right_turn_purpose": "right_turn", "through_purpose": "through",
                   "left_turn_purpose": "left_turn", "right_turn_route_mismatch": "right_turn"}[suffix]
        route = "other" if suffix == "right_turn_route_mismatch" else "right_turn"
        return {"assignment_id": AID, "case_id": AID + "__" + suffix,
                "source_kind": "original_native_map_geometry", "reviewed_original_native_site": True,
                "source_id": "synthetic-only", "map_name": "synthetic", "map_sha256": "a" * 64,
                "highway_source": "synthetic-highway", "turn_lane_source": "synthetic-lane",
                "connected_route_source": "synthetic-route", "driver_actor_id": "driver",
                "public_highway": True, "one_right_turn_lane": True, "exclusive_right_turn": True,
                "native_ids": {"entry_road": 1, "turn_lane": -1, "right_exit_road": 2, "t_junction": 3},
                "connected_routes": {"right_turn": [1, 2]},
                "purpose_declaration": {"declared_purpose": purpose, "source_ref": "synthetic-purpose",
                                        "declared_before_frame": -1},
                "requested_departure_route": route,
                "alternate_exit": {"source": "synthetic-alternate", "road_id": 4},
                "native_spawn": {"source_id": "synthetic-pose", "blueprint_id": "vehicle.synthetic",
                                 "pose_xyz_ypr": [0, 0, 0, 0, 0, 0]},
                "trajectory": {"source_id": "synthetic-trajectory",
                               "right_turn": [[0, 0], [10, 0], [15, -5]],
                               "other": [[0, 0], [10, 0], [15, 5]]}}

    def test_four_exact_cases(self):
        for suffix in ("right_turn_purpose", "through_purpose", "left_turn_purpose",
                       "right_turn_route_mismatch"):
            site = self.site(suffix)
            request = construct(site, site["case_id"])
            self.assertEqual(request["case_id"], site["case_id"])

    def test_nonexclusive_lane_rejected(self):
        site = self.site()
        site["exclusive_right_turn"] = False
        with self.assertRaisesRegex(ValueError, "exclusive"):
            construct(site, site["case_id"])

    def test_late_purpose_rejected(self):
        site = self.site()
        site["purpose_declaration"]["declared_before_frame"] = 0
        with self.assertRaisesRegex(ValueError, "before initial"):
            construct(site, site["case_id"])

    def test_unconnected_exit_rejected(self):
        site = self.site()
        site["connected_routes"]["right_turn"] = [1, 4]
        with self.assertRaisesRegex(ValueError, "connected"):
            construct(site, site["case_id"])


if __name__ == "__main__":
    unittest.main()
