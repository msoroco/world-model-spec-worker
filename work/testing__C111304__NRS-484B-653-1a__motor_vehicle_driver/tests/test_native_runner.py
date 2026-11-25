import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_runner
from test_carla_adapter import Carla, World, cameras, site


class NativeRunnerTests(unittest.TestCase):
    def test_materialized_bundle_directory_accepts_source_gated_capture(self):
        world = World()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            camera_file = root / 'camera.json'
            camera_file.write_text(json.dumps(cameras()), encoding='utf-8')
            for name in ('site.json', 'access.txt', 'review.json'):
                (root / name).write_text('source', encoding='utf-8')
            output = root / 'attempt'
            output.mkdir()
            (output / 'config.json').write_text('{}', encoding='utf-8')
            (output / 'runner.py').write_text('# materialized runner\n', encoding='utf-8')
            paths = [root / name for name in
                     ('site.json', 'access.txt', 'review.json', 'camera.json')]
            with patch.object(native_runner, 'bind_world_site', return_value=site()), \
                 patch.object(native_runner, 'capture', return_value={'passed': True}) as capture:
                receipt = native_runner.run(world, Carla, 'person_north_early', *paths, output)
            self.assertEqual(receipt, {'passed': True})
            self.assertTrue(capture.called)
            self.assertTrue((output / 'config.json').is_file())
            self.assertTrue((output / 'site.json').is_file())
            self.assertFalse(world.settings.synchronous_mode)

    def test_source_review_is_required_before_world_mutation(self):
        world = World()
        with TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in
                     ('site.json', 'access.txt', 'review.json', 'camera.json')]
            with self.assertRaisesRegex(ValueError, 'site source missing'):
                native_runner.run(world, Carla, 'person_north_early', *paths, Path(tmp))
        self.assertFalse(world.settings.synchronous_mode)
        self.assertEqual(world.actors, [])

    def test_owned_world_restored_after_capture_failure(self):
        world = World()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            camera_file = root / 'camera.json'
            camera_file.write_text(json.dumps(cameras()), encoding='utf-8')
            for name in ('site.json', 'access.txt', 'review.json'):
                (root / name).write_text('source', encoding='utf-8')
            output = root / 'attempt'
            output.mkdir()
            paths = [root / name for name in
                     ('site.json', 'access.txt', 'review.json', 'camera.json')]
            with patch.object(native_runner, 'bind_world_site', return_value=site()), \
                 patch.object(native_runner, 'capture', side_effect=ValueError('original camera failure')):
                with self.assertRaisesRegex(ValueError, 'original camera failure'):
                    native_runner.run(world, Carla, 'person_south_early', *paths, output)
            self.assertFalse(world.settings.synchronous_mode)
            self.assertTrue(world.actors)
            self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == '__main__':
    unittest.main()
