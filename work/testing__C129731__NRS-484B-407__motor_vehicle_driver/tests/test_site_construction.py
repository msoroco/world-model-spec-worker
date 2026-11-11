import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from site_construction import load_site, spawned_occluder, validate_site


def site():
    def lane(xsign, road):
        return {"road_id": road, "lane_id": xsign,
                "stations": [{"distance_to_turn_m": d, "xyz_m": [xsign*d, 0, 0]}
                             for d in (5, 80, 160)]}
    return {"law_id": "NRS-484B-407", "cell_id": "C129731",
            "actor": "motor_vehicle_driver", "source_status": "diagnostic_fixture",
            "map_name": "SyntheticCurveFixture", "feature": "curve",
            "turn_site_xyz_m": [0, 0, 0],
            "centerline_xyz_m": [[-160, 0, 0], [0, 0, 0], [160, 10, 0]],
            "incoming_lanes": {"approach_a": lane(-1, 10), "approach_b": lane(1, 10)},
            "u_turn_route_xyz_m": [[-10, 0, 0], [0, 0, 0], [4, 3, 0], [-5, 5, 0], [-10, 5, 0]],
            "occluder": {"blueprint_id": "static.prop.fixture_wall",
                         "center_xyz_m": [-100, 0, 1.5], "half_extent_xyz_m": [2, 2, 2],
                         "yaw_deg": 0, "target_direction": "approach_a"}}


class SiteConstructionTests(unittest.TestCase):
    def test_curve_and_crest_require_actual_shape_and_two_lanes(self):
        validate_site(site())
        flat = site(); flat["centerline_xyz_m"][-1][1] = 0
        with self.assertRaisesRegex(ValueError, "no constructed curve"):
            validate_site(flat)
        crest = site(); crest["feature"] = "crest"
        crest["centerline_xyz_m"] = [[-160, 0, 0], [0, 0, 8], [160, 0, 0]]
        validate_site(crest)
        crest["centerline_xyz_m"][1][2] = 0
        with self.assertRaisesRegex(ValueError, "no constructed grade crest"):
            validate_site(crest)
        same = site(); same["incoming_lanes"]["approach_b"]["lane_id"] = -1
        with self.assertRaisesRegex(ValueError, "Distinct surveyed road/lane"):
            validate_site(same)

    def test_occluder_intersects_planned_line_and_u_turn_reverses(self):
        alternate = site(); alternate["occluder"]["center_xyz_m"][1] = 15
        with self.assertRaisesRegex(ValueError, "does not intersect"):
            validate_site(alternate)
        low = site(); low["occluder"]["center_xyz_m"][2] = -5
        with self.assertRaisesRegex(ValueError, "does not intersect"):
            validate_site(low)
        wrong_route = site(); wrong_route["u_turn_route_xyz_m"][-1] = [10, 5, 0]
        with self.assertRaisesRegex(ValueError, "does not reverse"):
            validate_site(wrong_route)

    def test_hash_bound_source_and_actor_lifecycle(self):
        value = site()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "site.json"
            path.write_text(json.dumps(value))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "Diagnostic geometry"):
                load_site(path, digest)
            with self.assertRaisesRegex(ValueError, "Site packet changed"):
                load_site(path, "0" * 64)
            candidate = site(); candidate["source_status"] = "reviewed_candidate"
            path.write_text(json.dumps(candidate))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(load_site(path, digest)["feature"], "curve")
        calls = []
        actor = NS(destroy=lambda: calls.append("destroy"),
                   bounding_box=NS(extent=NS(x=2.5, y=2.5, z=2.5)))
        world = NS(get_blueprint_library=lambda: NS(find=lambda name: calls.append(name) or NS()),
                   try_spawn_actor=lambda bp, pose: calls.append("spawn") or actor)
        carla = NS(Location=lambda **kw: NS(**kw), Rotation=lambda **kw: NS(**kw),
                   Transform=lambda loc, rot: (loc, rot))
        with spawned_occluder(world, carla, value) as spawned:
            self.assertIs(spawned, actor)
        self.assertEqual(calls, ["static.prop.fixture_wall", "spawn", "destroy"])
        actor.bounding_box.extent.x = 1
        with self.assertRaisesRegex(ValueError, "smaller than declared"):
            with spawned_occluder(world, carla, value):
                pass
        self.assertEqual(calls[-1], "destroy")


if __name__ == "__main__":
    unittest.main()
