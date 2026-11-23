import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("center_lane_site", ROOT / "center_lane_site.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def site():
    source = {"path": "native/map.json", "sha256": "a" * 64}
    lanes = [
        {"id": "center", "road_id": 42, "center_turn_lane": True, "exclusive_turn_use": True,
         "permitted_turn_directions": ["negative", "positive"], "centreline_xy_m": [[0, 0], [100, 0]]},
        {"id": "east", "road_id": 42, "receiving_through": True, "centreline_xy_m": [[0, -3], [100, -3]]},
        {"id": "west", "road_id": 42, "opposing_through": True, "centreline_xy_m": [[100, 3], [0, 3]]},
    ]
    return {"native_map_source": source, "highway_review_source": {"path": "review/highway.json", "sha256": "b" * 64},
            "public_highway_confirmed": True, "lanes": lanes, "entry_maneuver": "left_turn_onto_highway",
            "entry_target_lane_id": "center", "merge_target_lane_id": "east"}


class SiteTests(unittest.TestCase):
    def test_source_gated_opposite_approaches(self):
        p = site()
        self.assertEqual(MODULE.validate_site(p)["center_lane_id"], "center")
        p["lanes"][1]["centreline_xy_m"] = [[100, -3], [0, -3]]
        p["lanes"][2]["centreline_xy_m"] = [[0, 3], [100, 3]]
        self.assertEqual(MODULE.validate_site(p)["opposing_lane_id"], "west")

    def test_unreviewed_highway_rejected(self):
        p = site()
        p["public_highway_confirmed"] = False
        with self.assertRaisesRegex(ValueError, "public-highway"):
            MODULE.validate_site(p)

    def test_second_center_lane_rejected(self):
        p = site()
        p["lanes"].append(dict(p["lanes"][0], id="center2"))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            MODULE.validate_site(p)

    def test_ordinary_two_way_left_turn_lane_rejected(self):
        p = site()
        p["lanes"][0]["exclusive_turn_use"] = False
        with self.assertRaisesRegex(ValueError, "exclusive"):
            MODULE.validate_site(p)

    def test_same_direction_through_lanes_rejected(self):
        p = site()
        p["lanes"][2]["centreline_xy_m"] = [[0, 3], [100, 3]]
        with self.assertRaisesRegex(ValueError, "not opposing"):
            MODULE.validate_site(p)

    def test_wrong_merge_target_rejected(self):
        p = site()
        p["merge_target_lane_id"] = "west"
        with self.assertRaisesRegex(ValueError, "targets mismatch"):
            MODULE.validate_site(p)


if __name__ == "__main__":
    unittest.main()
