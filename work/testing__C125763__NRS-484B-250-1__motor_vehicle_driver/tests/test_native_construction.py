"""Source and two-direction construction tests with a fake Native world."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125763_native_construction", ROOT / "native_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeMap:
    def to_opendrive(self):
        return "<OpenDRIVE reviewed='fixture'/>"

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError("reviewed route must not project to another lane")
        return SimpleNamespace(road_id=1 if location.y == 0 else 2, lane_id=-1)


class FakeActor:
    def __init__(self, identity):
        self.id = identity
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self):
        self.actors = []
        self.fail_second = False

    def get_map(self):
        return FakeMap()

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: name)

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and len(self.actors) == 1:
            return None
        actor = FakeActor(len(self.actors) + 10)
        self.actors.append(actor)
        return actor


class FakeCarla:
    @staticmethod
    def Location(**kwargs):
        return SimpleNamespace(**kwargs)

    @staticmethod
    def Rotation(**kwargs):
        return SimpleNamespace(**kwargs)

    @staticmethod
    def Transform(location, rotation):
        return SimpleNamespace(location=location, rotation=rotation)


class ReviewedConstructionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = FakeWorld()
        (self.root / "device.txt").write_text("fixture yield sign\n", encoding="utf-8")
        (self.root / "highway.txt").write_text("fixture roads A and B\n", encoding="utf-8")
        def binding(name):
            return {"path": name, "sha256": module._sha(self.root / name),
                    "citation": "diagnostic fixture only"}
        self.site = {
            "assignment_id": module.ASSIGNMENT, "cell_id": "C125763",
            "control": "yield_sign", "maneuver": "travel",
            "review_status": "diagnostic_fixture", "reviewer": "CPU fixture",
            "map_source_citation": "diagnostic fixture only",
            "highway_source_citation": "diagnostic fixture only",
            "device_source_citation": "diagnostic fixture only",
            "crossing_id": "fixture crossing", "roadway_id": "fixture roadway",
            "intersection_polygon_xy_m": [[-1, -1], [2, -1], [2, 1], [-1, 1]],
            "map_sha256": hashlib.sha256(FakeMap().to_opendrive().encode()).hexdigest(),
            "device_source": binding("device.txt"),
            "highway_source": binding("highway.txt"),
            "ego_highway": "A", "other_highway": "B",
            "approach_relation": "crossing", "ego_side": "left", "other_side": "right",
            "official_yield_sign_present": True,
            "yield_sign_controls_intersection": True,
            "subsection_4_reviewed": False,
            "subsection_4_source_citation": "NRS 484B.250(4) exported exact text",
            "ego_route": [[-5, 0, 0], [-1, 0, 0], [2, 0, 0]],
            "other_route": [[1, -5, 0], [1, -1, 0], [1, 2, 0]],
            "ego_lane": {"road_id": 1, "lane_id": -1},
            "other_lane": {"road_id": 2, "lane_id": -1},
            "ego_blueprint": "vehicle.fixture.ego",
            "other_blueprint": "vehicle.fixture.other",
            "release_s": {"precedence": 6.0, "advance": 3.0},
            "other_release_s": 1.0,
        }
        self.write()

    def write(self):
        (self.root / "site.json").write_text(json.dumps(self.site), encoding="utf-8")

    def test_two_original_approaches_and_cleanup(self):
        scene = module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)
        pair = module.spawn_pair(self.world, FakeCarla, scene)
        self.assertEqual([actor.id for actor in pair], [10, 11])
        self.assertEqual(scene["ego_lane"]["road_id"], 1)
        self.assertEqual(scene["other_lane"]["road_id"], 2)
        self.world = FakeWorld()
        self.world.fail_second = True
        with self.assertRaisesRegex(RuntimeError, "other"):
            module.spawn_pair(self.world, FakeCarla, scene)
        self.assertTrue(self.world.actors[0].destroyed)

    def test_production_rejects_diagnostic_and_stale_sources(self):
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            module.reviewed_scene(self.root / "site.json", self.world)
        (self.root / "device.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bytes absent or stale"):
            module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)

    def test_live_map_lane_and_exception_source_are_required(self):
        self.site["map_sha256"] = "0" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "live OpenDRIVE"):
            module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)
        self.site["map_sha256"] = hashlib.sha256(FakeMap().to_opendrive().encode()).hexdigest()
        self.site["subsection_4_source_citation"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "subsection-4"):
            module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)
        self.site["subsection_4_source_citation"] = "NRS 484B.250(4)"
        self.site["other_lane"]["road_id"] = 9
        self.write()
        scene = module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)
        with self.assertRaisesRegex(ValueError, "other"):
            module.spawn_pair(self.world, FakeCarla, scene)
        self.assertTrue(self.world.actors[0].destroyed)

    def test_no_same_highway_or_same_release_schedule(self):
        self.site["other_highway"] = "A"
        self.write()
        with self.assertRaisesRegex(ValueError, "different-highway"):
            module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)
        self.site["other_highway"] = "B"
        self.site["release_s"]["advance"] = 6.0
        self.write()
        with self.assertRaisesRegex(ValueError, "distinct reviewed ego response"):
            module.reviewed_scene(self.root / "site.json", self.world, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
