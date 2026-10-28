import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace as N

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
from scene_model import route
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore


class PackageTests(unittest.TestCase):
    def test_case_route_and_offline(self):
        runner.check()
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertGreater(len(route(config['mode'], config['case'])), 200)

    def test_actual_frame_writer_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'frames.jsonl'
            with FrameMap(path) as frame_map:
                frame_map.append(41, .05, source_frames={'view0': {'source_bgra_sha256': 'x'}})
                with self.assertRaises(ValueError):
                    frame_map.append(41, .1)
            record = json.loads(path.read_text().splitlines()[0])
            self.assertEqual((record['video_frame'], record['carla_frame'], record['native_frame']), (0,41,41))

    def test_failed_cleanup_does_not_skip_restore(self):
        events, errors = [], []
        def fail():
            events.append('sensor_stop')
            raise RuntimeError('sensor')
        runner.cleanup_action(errors, 'sensor', fail)
        runner.cleanup_action(errors, 'restore', lambda: events.append('restore'))
        self.assertEqual(events, ['sensor_stop', 'restore'])
        self.assertEqual(len(errors), 1)

    def test_generated_world_restore_and_bad_readback(self):
        class World:
            def __init__(self, xodr):
                self.xodr = xodr
                self.settings = N(synchronous_mode=False, fixed_delta_seconds=None)
                self.weather = N(cloudiness=1.)
            def get_map(self): return N(name='OpenDriveMap', to_opendrive=lambda: self.xodr)
            def get_settings(self): return self.settings
            def get_weather(self): return self.weather
            def apply_settings(self, value): self.settings = value
            def set_weather(self, value): self.weather = value
        class Client:
            def __init__(self): self.world = World('source')
            def get_world(self): return self.world
            def get_available_maps(self): return ['Town01']
            def generate_opendrive_world(self, xodr): self.world = World(xodr)
        client = Client()
        saved = snapshot(client)
        client.world = World('changed')
        self.assertTrue(restore(client, saved)['restored'])
        client.generate_opendrive_world = lambda x: None
        client.world = World('changed')
        with self.assertRaisesRegex(ValueError, 'OpenDRIVE readback'):
            restore(client, saved)


if __name__ == '__main__': unittest.main()
