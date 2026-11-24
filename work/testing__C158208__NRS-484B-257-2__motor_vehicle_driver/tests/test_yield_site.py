import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("yield_site", ROOT / "yield_site.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class SiteTests(unittest.TestCase):
    def test_authored_one_way_to_two_way_yield_connections(self):
        receipt = site.validate_authored_site()
        self.assertEqual(receipt["ego_approach_road_id"], 158208)
        self.assertEqual(receipt["other_approach_road_ids"], [158212, 158214])
        self.assertEqual(receipt["non_through_highway_judgment"], "unresolved")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changed.xodr"
            path.write_text(site.ROAD.read_text().replace('type="205"', 'type="206"'))
            with self.assertRaisesRegex(ValueError, "yield sign"):
                site.validate_authored_site(path)

    def test_native_readback_requires_exact_lanes_and_governing_trigger(self):
        probes = {(-20, 1.8): (158208, -1, False), (0, 1.8): (158210, -1, True),
                  (1.8, 20): (158212, -1, False), (1.8, 0): (158213, -1, True),
                  (-1.8, -20): (158214, 1, False)}

        def get_waypoint(point, project_to_road=False):
            road_id, lane_id, junction = probes[(point.x, point.y)]
            return NS(road_id=road_id, lane_id=lane_id, is_junction=junction)

        class Actors(list):
            def filter(self, pattern):
                return self

        sign = NS(id=88, trigger_volume=NS(contains=lambda point, transform: True),
                  get_transform=lambda: None)
        world = NS(get_map=lambda: NS(name="signed-map", get_waypoint=get_waypoint),
                   get_actors=lambda: Actors([sign]))
        location = lambda x, y, z: NS(x=x, y=y, z=z)
        self.assertEqual(site.validate_native_site(world, location_factory=location)["native_yield_sign_id"], 88)
        probes[(0, 1.8)] = (158210, -1, False)
        with self.assertRaisesRegex(ValueError, "road/lane"):
            site.validate_native_site(world, location_factory=location)

    def test_other_obligated_variant_has_actual_stop_control(self):
        receipt = site.validate_authored_site(site.ROAD_OTHER_STOP, other_stop=True)
        self.assertEqual(receipt["other_stop_signal_id"], "1582121")
        with self.assertRaisesRegex(ValueError, "selected other stop"):
            site.validate_authored_site(site.ROAD, other_stop=True)

        probes = {(-20, 1.8): (158208, -1, False), (0, 1.8): (158210, -1, True),
                  (1.8, 20): (158212, -1, False), (1.8, 0): (158213, -1, True),
                  (-1.8, -20): (158214, 1, False)}

        def get_waypoint(point, project_to_road=False):
            road_id, lane_id, junction = probes[(point.x, point.y)]
            return NS(road_id=road_id, lane_id=lane_id, is_junction=junction)

        class Actors:
            def __init__(self, with_stop):
                self.with_stop = with_stop

            def filter(self, pattern):
                if pattern == "traffic.stop*" and not self.with_stop:
                    return []
                return [NS(id=90 if pattern == "traffic.stop*" else 88,
                           trigger_volume=NS(contains=lambda point, transform: True),
                           get_transform=lambda: None)]

        actors = Actors(True)
        world = NS(get_map=lambda: NS(name="signed-map", get_waypoint=get_waypoint),
                   get_actors=lambda: actors)
        location = lambda x, y, z: NS(x=x, y=y, z=z)
        self.assertEqual(site.validate_native_site(world, other_stop=True,
                                                   location_factory=location)["native_other_stop_sign_id"], 90)
        actors.with_stop = False
        with self.assertRaisesRegex(ValueError, "stop sign governing other"):
            site.validate_native_site(world, other_stop=True, location_factory=location)


if __name__ == "__main__":
    unittest.main()
