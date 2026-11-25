import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from test_native_site import CARLA, World, request, SITE


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_adapter", ROOT / "native_adapter.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class Actor:
    def __init__(self, actor_id, blueprint_id):
        self.id = actor_id
        self.type_id = blueprint_id
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class LiveWorld(World):
    def __init__(self, missing_person=False):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.actors = []
        self.person = None if missing_person else Actor(42, "walker.person")

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(len(self.actors) + 1, blueprint.id)
        self.actors.append(actor)
        return actor

    def get_actor(self, actor_id):
        return self.person if self.person and actor_id == self.person.id else None


CARLA.Transform = lambda location, rotation: SimpleNamespace(location=location, rotation=rotation)
CARLA.Rotation = lambda **values: SimpleNamespace(**values)


class NativeAdapterTests(unittest.TestCase):
    def test_reviewed_live_setup_and_restoration(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = SITE.survey(LiveWorld(), CARLA, request(base), base / "survey")
            world = LiveWorld()
            with ADAPTER.OwnedEncounter(world, CARLA, base / "survey", refs["site"], "bicycle") as opened:
                self.assertEqual(opened.actors["person"].id, 42)
                self.assertEqual(opened.actors["rider"].type_id, "vehicle.bicycle")
                self.assertTrue(world.settings.synchronous_mode)
                self.assertEqual(world.settings.fixed_delta_seconds, 0.05)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertIsNone(world.settings.fixed_delta_seconds)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertFalse(world.person.destroyed)

    def test_missing_person_fails_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = SITE.survey(LiveWorld(), CARLA, request(base), base / "survey")
            world = LiveWorld(missing_person=True)
            with self.assertRaisesRegex(ValueError, "rider person actor unavailable"):
                with ADAPTER.OwnedEncounter(world, CARLA, base / "survey", refs["site"], "bicycle"):
                    pass
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == "__main__":
    unittest.main()
