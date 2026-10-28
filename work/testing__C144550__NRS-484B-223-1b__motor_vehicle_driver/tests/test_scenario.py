import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from runner import capture_frame, cleanup_action, route
from analyze import lane_change_events
from worker_exchange.native_output import FrameMap
from worker_exchange.world_restore import snapshot, restore


class World:
    def __init__(self, name='OpenDriveMap', xodr='original'):
        self.name, self.xodr = name, xodr
        self.settings = N(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = N(cloudiness=5.0)

    def get_map(self):
        return N(name=self.name, to_opendrive=lambda: self.xodr)

    def get_settings(self):
        return self.settings

    def get_weather(self):
        return self.weather

    def apply_settings(self, value):
        self.settings = value

    def set_weather(self, value):
        self.weather = value


class Client:
    def __init__(self, name='OpenDriveMap'):
        self.world = World(name)
        self.calls = []

    def get_world(self):
        return self.world

    def get_available_maps(self):
        return ['Town01']

    def load_world(self, name):
        self.calls.append(('load', name))
        self.world = World(name)

    def generate_opendrive_world(self, xodr):
        self.calls.append(('generate', xodr))
        self.world = World(xodr=xodr)


class PilotTests(unittest.TestCase):
    def test_signal_lead_uses_actual_path_and_separate_body_crossing(self):
        points = [{'x': -2, 'y': -1.75}, {'x': -1, 'y': -1.75},
                  {'x': 0, 'y': -1.6}, {'x': 1, 'y': -3}]
        source = [{'native_light_state': 'LeftBlinker', 'ego_body_vertices_m': [[-2,-2.5,0]]},
                  {'native_light_state': 'LeftBlinker', 'ego_body_vertices_m': [[-1,-2.5,0]]},
                  {'native_light_state': 'LeftBlinker', 'ego_body_vertices_m': [[0,-2.6,0]]},
                  {'native_light_state': 'LeftBlinker', 'ego_body_vertices_m': [[1,-3.7,0]]}]
        signal, movement, boundary, lead = lane_change_events(points, source)
        self.assertEqual((signal, movement, boundary), (0, 2, 3))
        self.assertGreater(lead, 2.0)

    def test_route_reaches_northbound_right_half(self):
        points = route(1.75)
        self.assertLess(points[0][1], 0)
        self.assertGreater(points[-1][1], 70)
        self.assertEqual(points[-1][0], 1.75)

    def test_mode_specific_routes(self):
        self.assertEqual(route(1.75, 'left_turn', -1.75)[-1][0], -1.75)
        self.assertEqual(route(1.75, 'lane_change')[-1][1], -5.25)
        self.assertEqual(route(1.75, 'stop')[-1][0], -9)
        self.assertEqual(route(1.75, 'following')[-1][1], -1.75)

    def test_capture_side_frame_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'video_frames.jsonl'
            with FrameMap(path) as frame_map:
                row = capture_frame(frame_map, 41, .05, {'view0': {'width': 1920}})
                self.assertEqual((row['video_frame'], row['carla_frame'], row['native_frame']), (0, 41, 41))
                with self.assertRaises(ValueError):
                    capture_frame(frame_map, 41, .1, {})
            self.assertEqual(len(path.read_text().splitlines()), 1)
            with self.assertRaises(FileExistsError):
                FrameMap(path)

    def test_generated_and_packaged_restoration(self):
        for name, method in [('OpenDriveMap', 'generate'), ('Town01', 'load')]:
            client = Client(name)
            saved = snapshot(client)
            client.world = World('changed', 'changed')
            receipt = restore(client, saved)
            self.assertTrue(receipt['restored'])
            self.assertEqual(client.calls[0][0], method)

    def test_failed_readback_and_cleanup_continuation(self):
        client = Client()
        saved = snapshot(client)
        client.generate_opendrive_world = lambda x: None
        client.world = World(xodr='changed')
        with self.assertRaisesRegex(ValueError, 'OpenDRIVE readback'):
            restore(client, saved)
        failures, calls = [], []
        cleanup_action(failures, 'first', lambda: (_ for _ in ()).throw(RuntimeError('failure')))
        cleanup_action(failures, 'restore', lambda: calls.append('restored'))
        self.assertEqual(calls, ['restored'])
        self.assertEqual(len(failures), 1)


if __name__ == '__main__':
    unittest.main()
