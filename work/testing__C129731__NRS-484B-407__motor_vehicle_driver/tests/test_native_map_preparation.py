import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from native_map_preparation import load_verified_world


class NativeMapPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = PACKAGE / "native-map-plan"
        cls.source_site = json.loads((cls.plan / "approach_to_crest__occluded_approach_b.json").read_text())

    def test_unreviewed_source_is_rejected_before_world_mutation(self):
        calls = []
        client = NS(generate_opendrive_world=lambda source: calls.append(source))
        with self.assertRaisesRegex(ValueError, "Unreviewed diagnostic"):
            load_verified_world(client, NS(Location=lambda **kw: NS(**kw)),
                                self.source_site, self.plan)
        self.assertEqual(calls, [])

    def test_reviewed_packet_loads_source_and_checks_all_six_stations(self):
        site = copy.deepcopy(self.source_site)
        site["source_status"] = "reviewed_candidate"
        site["map_source"]["status"] = "reviewed_candidate"
        seen = []
        def waypoint(location, project_to_road):
            self.assertFalse(project_to_road)
            seen.append((location.x, location.y, location.z))
            return NS(road_id=10, lane_id=-1 if location.y < 0 else 1,
                      transform=NS(location=location))
        world = NS(get_map=lambda: NS(get_waypoint=waypoint))
        calls = []
        client = NS(generate_opendrive_world=lambda source: calls.append(source),
                    get_world=lambda: world)
        self.assertIs(load_verified_world(client, NS(Location=lambda **kw: NS(**kw)),
                                          site, self.plan), world)
        self.assertEqual(len(calls), 1)
        self.assertIn("<OpenDRIVE", calls[0])
        self.assertEqual(len(seen), 6)

        site["map_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "OpenDRIVE source changed"):
            load_verified_world(client, NS(Location=lambda **kw: NS(**kw)), site, self.plan)
        self.assertEqual(len(calls), 1)

    def test_native_lane_and_position_mismatch_are_rejected(self):
        site = copy.deepcopy(self.source_site)
        site["source_status"] = "reviewed_candidate"
        site["map_source"]["status"] = "reviewed_candidate"
        def run(mapper):
            world = NS(get_map=lambda: NS(get_waypoint=mapper))
            client = NS(generate_opendrive_world=lambda source: None,
                        get_world=lambda: world)
            return load_verified_world(client, NS(Location=lambda **kw: NS(**kw)),
                                       site, self.plan)
        with self.assertRaisesRegex(ValueError, "lane differs"):
            run(lambda location, project_to_road: NS(
                road_id=10, lane_id=1, transform=NS(location=location)))
        with self.assertRaisesRegex(ValueError, "waypoint differs"):
            run(lambda location, project_to_road: NS(
                road_id=10, lane_id=-1 if location.y < 0 else 1,
                transform=NS(location=NS(x=location.x + 2, y=location.y, z=location.z))))
        changed = copy.deepcopy(site)
        changed["map_source"]["path"] = "../crest-road.xodr"
        with self.assertRaisesRegex(ValueError, "Invalid relative"):
            load_verified_world(NS(), NS(), changed, self.plan)


if __name__ == "__main__":
    unittest.main()
