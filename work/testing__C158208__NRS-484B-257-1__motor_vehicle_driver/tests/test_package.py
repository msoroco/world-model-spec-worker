import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N

import runner
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore


class World:
    def __init__(self, name='OpenDriveMap', xodr='source'):
        self.name, self.xodr = name, xodr
        self.settings = N(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = N(cloudiness=1.0)
    def get_map(self):
        return N(name=self.name, to_opendrive=lambda: self.xodr)
    def get_settings(self): return self.settings
    def get_weather(self): return self.weather
    def apply_settings(self, value): self.settings = value
    def set_weather(self, value): self.weather = value


class Client:
    def __init__(self, name='OpenDriveMap'):
        self.world, self.calls = World(name), []
    def get_world(self): return self.world
    def get_available_maps(self): return ['Town01']
    def load_world(self, name):
        self.calls.append(('load', name)); self.world = World(name)
    def generate_opendrive_world(self, xodr):
        self.calls.append(('generate', xodr)); self.world = World(xodr=xodr)


class PackageTests(unittest.TestCase):
    def test_check_and_route(self):
        runner.check()
        config = json.loads((runner.ROOT / 'config.json').read_text())
        points = runner.route(config, config['case'])
        self.assertGreater(len(points), 40)
        self.assertEqual(list(points[-1]), config['route_end_m'])

    def test_capture_side_original_frame_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'frames.jsonl'
            with FrameMap(path) as writer:
                writer.append(21714, .05, source_frames={'view0': {'width': 1920}})
                with self.assertRaises(ValueError): writer.append(21714, .1)
                writer.append(21715, .1)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([(r['video_frame'], r['carla_frame'], r['native_frame']) for r in records],
                             [(0, 21714, 21714), (1, 21715, 21715)])

    def test_cleanup_failure_continues_to_restore(self):
        called, failures = [], []
        def fail(): raise RuntimeError('sensor stop failed')
        runner.cleanup_action(failures, 'sensor stop', fail)
        runner.cleanup_action(failures, 'world restore', lambda: called.append('restore'))
        self.assertEqual(called, ['restore'])
        self.assertEqual(len(failures), 1)

    def test_generated_and_packaged_restore_readback(self):
        generated = Client()
        saved = snapshot(generated)
        generated.world = World(xodr='changed')
        self.assertTrue(restore(generated, saved)['restored'])
        self.assertEqual(generated.calls, [('generate', 'source')])
        packaged = Client('Town01')
        saved = snapshot(packaged)
        self.assertTrue(restore(packaged, saved)['restored'])
        self.assertEqual(packaged.calls, [('load', 'Town01')])

    def test_bad_restore_readback_rejected(self):
        client = Client()
        saved = snapshot(client)
        client.generate_opendrive_world = lambda xodr: None
        client.world = World(xodr='changed')
        with self.assertRaisesRegex(ValueError, 'OpenDRIVE readback'):
            restore(client, saved)

    def test_source_gap_and_overlap_are_body_based(self):
        config = {'crosswalk_box_m': [-2, 2, -5, 5]}
        point = {'position_m': [0, 0, 0], 'heading_deg': 0, 'speed_mps': 0,
                 'control': {'reverse': True}}
        event = {'original_observations': {'participants': []},
                 'world': {'road_projection': {'road_id': 1}}}
        body = [[0, 0, 0], [1, 1, 0]]
        other = {'body_vertices_m': [[11, 0, 0], [12, 1, 0]]}
        values = runner.source_values(config, point, event, 3, body, other, 7)
        self.assertEqual(values['surface_gap']['gap_m'], 10)
        self.assertTrue(values['crosswalk_overlap']['body_overlap'])
        self.assertTrue(values['crosswalk_overlap']['reverse_control'])


if __name__ == '__main__': unittest.main()
