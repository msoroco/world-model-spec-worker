import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime'))
from owned_capture import capture_owned
import test_native_capture as fixture

World = fixture.World
CASE = fixture.CASE
control = fixture.control
media_factory = fixture.media_factory
transform = fixture.transform


class OwnedWorld(World):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = SimpleNamespace(synchronous_mode=False,
                                        fixed_delta_seconds=0.1)
        self.weather = SimpleNamespace(cloudiness=17.0)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_weather(self):
        return self.weather

    def set_weather(self, weather):
        self.weather = weather


class Client:
    def __init__(self, world):
        self.world = world
        self.loads = 0

    def get_world(self):
        return self.world

    def get_available_maps(self):
        return [self.world.map.name]

    def load_world(self, name):
        if name != self.world.map.name:
            raise ValueError('wrong map restoration')
        self.loads += 1


class IgnoredSettingsWorld(OwnedWorld):
    def apply_settings(self, settings):
        pass


class OwnedCaptureTests(unittest.TestCase):
    def _harness(self, *, miss_camera_at=None):
        harness = fixture.CaptureTests(methodName='test_full_diagnostic_capture_is_source_joined_and_decodable')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        world = OwnedWorld(miss_camera_at=miss_camera_at)
        harness.world = world
        return harness, Client(world)

    def test_success_restores_original_world_and_cleans_actors(self):
        harness, client = self._harness()
        receipt = capture_owned(client, harness.site, harness.attempt, CASE,
                                'owned-run', 0.05, transform, control,
                                diagnostic_fixture=True, media_factory=media_factory)
        self.assertEqual(receipt['capture_index']['frame_count'], 900)
        self.assertEqual(client.loads, 1)
        self.assertFalse(client.world.get_settings().synchronous_mode)
        self.assertEqual(client.world.get_settings().fixed_delta_seconds, 0.1)
        self.assertEqual(client.world.get_weather().cloudiness, 17.0)
        self.assertTrue(client.world.actor.destroyed)

    def test_failed_camera_capture_still_restores_original_world(self):
        harness, client = self._harness(miss_camera_at=103)
        with self.assertRaisesRegex(ValueError, 'original Native frame missing'):
            capture_owned(client, harness.site, harness.attempt, CASE,
                          'owned-fail', 0.05, transform, control,
                          diagnostic_fixture=True, media_factory=media_factory)
        self.assertEqual(client.loads, 1)
        self.assertFalse(client.world.get_settings().synchronous_mode)
        self.assertEqual(client.world.get_settings().fixed_delta_seconds, 0.1)
        self.assertTrue(client.world.actor.destroyed)
        self.assertTrue(all(sensor.destroyed for sensor in client.world.sensors))

    def test_settings_readback_failure_prevents_spawn_and_restores(self):
        harness, _ = self._harness()
        world = IgnoredSettingsWorld()
        client = Client(world)
        with self.assertRaisesRegex(ValueError, 'settings readback differs'):
            capture_owned(client, harness.site, harness.attempt, CASE,
                          'owned-readback', 0.05, transform, control,
                          diagnostic_fixture=True, media_factory=media_factory)
        self.assertEqual(client.loads, 1)
        self.assertIsNone(world.actor)
        self.assertFalse(world.get_settings().synchronous_mode)


if __name__ == '__main__':
    unittest.main()
