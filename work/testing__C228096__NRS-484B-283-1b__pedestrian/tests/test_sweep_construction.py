"""Exercise bounded engineering stations and preserve their evidence limits."""
import sys
from pathlib import Path
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_diagnostic_specs import scene
from curb_entry import CASES, construct
from sweep_construction import STATIONS, planned_scene


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            if name.startswith("spawn_"):
                return name
        return call


class SweepConstructionTests(unittest.TestCase):
    def test_all_stations_construct_distinct_original_requests(self):
        base = scene(CASES[0])
        seen = set()
        for station in STATIONS:
            with self.subTest(station=station.name):
                planned = planned_scene(base, station)
                adapter = FakeAdapter()
                construct(adapter, planned, CASES[0])
                self.assertIn("set_pedestrian_route", [x[0] for x in adapter.calls])
                self.assertIn("set_vehicle_route", [x[0] for x in adapter.calls])
                actual = (planned["departure_frame"],
                          tuple(planned["vehicle_route_xy"][0]))
                self.assertNotIn(actual, seen)
                seen.add(actual)
                self.assertIsNot(planned, base)
        self.assertEqual(len(seen), 6)

    def test_source_and_geometry_gates_are_preserved(self):
        base = scene(CASES[0])
        missing = dict(base)
        missing.pop("curb_safety_source_sha256")
        with self.assertRaisesRegex(ValueError, "original context missing"):
            planned_scene(missing, STATIONS[0])
        wrong_path = dict(base)
        wrong_path["vehicle_route_xy"] = [[-10, 1], [10, 1]]
        with self.assertRaisesRegex(ValueError, "path orientation"):
            planned_scene(wrong_path, STATIONS[-1])
        with self.assertRaisesRegex(ValueError, "unlisted"):
            from sweep_construction import Station
            planned_scene(base, Station("yield_impossibility", "invented", 5,
                                        "vehicle_distance_at_road_entry_m", "m"))


if __name__ == "__main__":
    unittest.main()
