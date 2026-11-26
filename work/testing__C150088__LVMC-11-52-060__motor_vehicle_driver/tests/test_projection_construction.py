"""CPU protocol checks for physically spawned projection parts."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection_construction import CASES, build_and_readback


SITE = {
    "reviewer": "source review fixture",
    "opendrive_sha256": "a" * 64,
    "curb_segment_start_m": [0.0, 0.0],
    "curb_segment_end_m": [40.0, 0.0],
    "street_side_reference_m": [0.0, 8.0],
    "vehicle_blueprint": "vehicle.fixture",
    "load_blueprint": "static.fixture_load",
    "trailer_blueprint": "vehicle.fixture_trailer",
    "street_jurisdiction": "reviewed Lakeview street fixture",
    "one_way_direction_source": "reviewed OpenDRIVE fixture",
}


class FakeAdapter:
    def __init__(self):
        self.actors = {}
        self.calls = []
        self.next_id = 0
        self.hitch_ok = True
        self.map_ok = True

    def provenance(self):
        return "original_native"

    def verify_loaded_map(self, digest):
        return self.map_ok and digest == "a" * 64

    def verify_curb(self, site, origin, tangent, normal):
        self.calls.append("verify_curb")
        return origin == (0.0, 0.0) and tangent == (1.0, 0.0) and normal == (0.0, 1.0)

    def _spawn(self, projection, parent=None):
        self.next_id += 1
        ident = self.next_id
        self.actors[ident] = {"projection": projection, "parent": parent}
        return ident

    def spawn_parked_vehicle(self, **kwargs):
        self.calls.append("spawn_parked_vehicle")
        return self._spawn(kwargs["outer_projection_m"])

    def parking_brake_readback(self, actor):
        return actor in self.actors

    def attach_physical_load(self, vehicle, **kwargs):
        self.calls.append("attach_physical_load")
        return self._spawn(kwargs["outer_projection_m"], vehicle)

    def attach_physical_trailer(self, vehicle, **kwargs):
        self.calls.append("attach_physical_trailer")
        return self._spawn(kwargs["outer_projection_m"], vehicle)

    def attachment_parent(self, actor):
        return self.actors[actor]["parent"]

    def hitch_readback(self, vehicle, trailer):
        return self.hitch_ok

    def actor_identity(self, actor):
        return "native-" + str(actor)

    def world_outline_xy(self, actor):
        y = self.actors[actor]["projection"]
        return [[10.0, y - 1], [12.0, y - 1], [12.0, y], [10.0, y]]

    def destroy(self, actor):
        self.calls.append("destroy")
        del self.actors[actor]


class ConstructionTest(unittest.TestCase):
    def test_exact_five_cases_create_and_read_back_original_parts(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                adapter = FakeAdapter()
                built = build_and_readback(adapter, SITE, case.case_id)
                self.assertAlmostEqual(built["original_projection_m"], case.projection_m)
                self.assertEqual(built["physical_parts"][-1]["category"], case.controlling_part)
                self.assertIn("spawn_parked_vehicle", adapter.calls)
                self.assertIn("verify_curb", adapter.calls)
                self.assertFalse(built["legal_equality_claimed"])

    def test_fallback_changes_only_parking_station(self):
        adapter = FakeAdapter()
        primary = build_and_readback(adapter, SITE, CASES[0].case_id)
        fallback = build_and_readback(adapter, SITE, CASES[0].case_id, candidate="fallback1")
        self.assertEqual(primary["original_projection_m"], fallback["original_projection_m"])
        self.assertEqual((primary["station_m"], fallback["station_m"]), (15.0, 18.0))

    def test_hitch_failure_destroys_owned_actors(self):
        adapter = FakeAdapter()
        adapter.hitch_ok = False
        with self.assertRaisesRegex(ValueError, "hitch Native readback"):
            build_and_readback(adapter, SITE, CASES[-1].case_id)
        self.assertEqual(adapter.actors, {})

    def test_map_mismatch_rejected_before_spawn(self):
        adapter = FakeAdapter()
        adapter.map_ok = False
        with self.assertRaisesRegex(ValueError, "map differs"):
            build_and_readback(adapter, SITE, CASES[0].case_id)
        self.assertNotIn("spawn_parked_vehicle", adapter.calls)

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown exact"):
            build_and_readback(FakeAdapter(), SITE, "other")


if __name__ == "__main__":
    unittest.main()
