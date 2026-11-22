"""Check that the spawn fallback preserves every comparison condition."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_driver import spawn_vehicles


def embedded(construction, name):
    return json.loads(next(item["content"] for item in construction["files"]
                           if item["path"] == name))


class SpawnFallbackTest(unittest.TestCase):
    def test_native_spawn_uses_alternate_start_after_primary_failure(self):
        manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
        entry = manifest["cases"][0]
        primary = embedded(json.loads((ROOT / entry["construction"]).read_text()), "scene.json")
        alternate = embedded(json.loads((ROOT / entry["candidates"][0]["construction"]).read_text()),
                             "scene.json")
        occupied = tuple(primary["ego_route_xy_m"][0])

        class Blueprint:
            def set_attribute(self, key, value):
                pass

        class Library:
            def filter(self, pattern):
                return [Blueprint()]

        class Actor:
            def __init__(self, identifier):
                self.id = identifier

            def destroy(self):
                pass

        class World:
            def __init__(self):
                self.calls = []

            def get_map(self):
                return object()

            def get_blueprint_library(self):
                return Library()

            def spawn_actor(self, blueprint, pose):
                point = (pose.location.x, pose.location.y)
                self.calls.append(point)
                return None if point == occupied else Actor(len(self.calls))

        def bound(mapping, scene, location_factory):
            def waypoint(point):
                location = type("Location", (), {"x": point[0], "y": point[1]})()
                transform = type("Transform", (), {"location": location})()
                return type("Waypoint", (), {"transform": transform})()
            return {party: [waypoint(scene[party + "_route_xy_m"][0])]
                    for party in ("ego", "other")}

        with patch("native_driver.bind_map", side_effect=bound):
            with self.assertRaisesRegex(ValueError, "Native spawn failed: ego"):
                spawn_vehicles(World(), primary, object())
            world = World()
            actors = spawn_vehicles(world, alternate, object())
        self.assertEqual(set(actors), {"ego", "other"})
        self.assertNotEqual(world.calls[0], occupied)

    def test_all_cases_change_only_initial_approach_points(self):
        manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 7)
        for entry in manifest["cases"]:
            with self.subTest(case=entry["case_id"]):
                primary = json.loads((ROOT / entry["construction"]).read_text())
                candidate = entry["candidates"][0]
                path = ROOT / candidate["construction"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 candidate["construction_sha256"])
                alternate = json.loads(path.read_text())
                self.assertEqual(embedded(primary, "config.json"),
                                 embedded(alternate, "config.json"))
                old = embedded(primary, "scene.json")
                new = embedded(alternate, "scene.json")
                for party in ("ego", "other"):
                    key = party + "_route_xy_m"
                    self.assertNotEqual(old[key][0], new[key][0])
                    self.assertEqual(old[key][1:], new[key][1:])
                    old.pop(key)
                    new.pop(key)
                self.assertEqual(old, new)
                self.assertTrue(json.loads((ROOT / candidate["compatibility"]["receipt"]).read_text())
                                ["passed"])


if __name__ == "__main__":
    unittest.main()
