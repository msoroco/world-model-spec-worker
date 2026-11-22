import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_binding_rehearsal import CarlaStandIn, RehearsalMap, RehearsalWorld, rehearse
from native_driver import spawn_vehicles
from opendrive_route_preflight import preflight


class BindingRehearsalTests(unittest.TestCase):
    def test_all_exact_diagnostic_cases_bind_and_reject_disconnection(self):
        proof = rehearse(ROOT)
        self.assertEqual(len(proof["cases"]), 7)
        self.assertTrue(all(item["disconnected_pre_spawn_rejected"]
                            for item in proof["cases"].values()))

    def test_source_hash_mismatch_rejected_before_spawn(self):
        path = ROOT / "scene.json"
        scene = json.loads(path.read_text())
        routes = preflight(ROOT / "connected-median-candidate.xodr", [path])["cases"][scene["case_id"]]
        source = (ROOT / "connected-median-candidate.xodr").read_text()
        world = RehearsalWorld(RehearsalMap(source + "\n", scene, routes))
        with self.assertRaisesRegex(ValueError, "map hash"):
            spawn_vehicles(world, scene, CarlaStandIn)
        self.assertEqual(world.spawned, [])

    def test_wrong_approach_road_rejected_before_spawn(self):
        path = ROOT / "scene.json"
        scene = json.loads(path.read_text())
        routes = preflight(ROOT / "connected-median-candidate.xodr", [path])["cases"][scene["case_id"]]
        source = (ROOT / "connected-median-candidate.xodr").read_text()
        world = RehearsalWorld(RehearsalMap(source, scene, routes))
        world.mapping.nodes[tuple(scene["other_route_xy_m"][0])].road_id = 999
        with self.assertRaisesRegex(ValueError, "approach road ID"):
            spawn_vehicles(world, scene, CarlaStandIn)
        self.assertEqual(world.spawned, [])


if __name__ == "__main__":
    unittest.main()
