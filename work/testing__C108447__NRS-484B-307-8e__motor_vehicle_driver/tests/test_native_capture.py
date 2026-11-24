import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
for name in ('property_route', 'route_controller', 'native_capture'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
capture = sys.modules['native_capture']


def packet():
    return {'source': {'kind': 'original_native_map_and_property_authority', 'path': '/reviewed/map.json', 'sha256': 'a' * 64},
            'coordinate_frame': 'native-map', 'intersecting_street_id': 'street-B',
            'properties': [{'id': 'lot', 'status': 'private', 'authority': 'original parcel authority',
                            'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
            'connector_routes': {'lot': [[-3, 5], [5, 5], [13, 5]]}}


class FakeEgo:
    def __init__(self, points):
        self.points = points
        self.index = 0
        self.controls = []

    def get_location(self):
        return types.SimpleNamespace(x=self.points[self.index][0], y=self.points[self.index][1])

    def get_velocity(self):
        return types.SimpleNamespace(x=2, y=0)

    def get_transform(self):
        return types.SimpleNamespace(rotation=types.SimpleNamespace(yaw=0))

    def apply_control(self, command):
        self.controls.append(command)


class FakeWorld:
    def __init__(self, ego, frames=None, times=None, delta=0.05):
        self.ego = ego
        self.frames = frames or list(range(1, len(ego.points) + 1))
        self.times = times
        self.delta = delta
        self.index = -1

    def tick(self):
        self.index += 1
        self.ego.index = min(self.index, len(self.ego.points) - 1)
        return self.frames[self.index]

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=True,
                                     fixed_delta_seconds=self.delta)

    def get_snapshot(self):
        elapsed = (self.times[self.index] if self.times is not None
                   else 40 + self.index / 20)
        return types.SimpleNamespace(
            frame=self.frames[self.index],
            timestamp=types.SimpleNamespace(elapsed_seconds=elapsed))


def signals(frame, name):
    return {'device_id': name, 'source': {'original_native_id': name},
            'facing_ego': name == 'approach_signal',
            'state': 'red_alone' if name == 'approach_signal' else 'green'}


class NativeCaptureTests(unittest.TestCase):
    def run_capture(self, points, **changes):
        ego = FakeEgo(points + [points[-1]] * (20 - len(points)))
        world = FakeWorld(ego, changes.pop('frames', None),
                          changes.pop('times', None), changes.pop('delta', 0.05))
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'original-route.json'
            args = dict(world=world, ego=ego, map_packet=packet(), property_id='lot', case_id='exact-case',
                        purpose={'source': 'authored intent', 'value': 'avoid_red'},
                        actor_source={'source': 'original actor registry', 'class': 'vehicle'},
                        signal_observer=signals, destination_street_id='street-B', output=output,
                        ticks=20, control_applier=lambda actor, command: actor.apply_control(command))
            args.update(changes)
            receipt = capture.capture(**args)
            trace = json.loads(output.read_text())
        return receipt, trace, ego

    def test_original_trace_records_every_signal_and_body_sample(self):
        receipt, trace, ego = self.run_capture([[-3, 5], [5, 5], [13, 5]])
        self.assertEqual(receipt['sample_count'], 20)
        self.assertEqual([s['frame'] for s in trace['approach_signal_history']], list(range(1, 21)))
        self.assertEqual(trace['destination_entry_frame'], 3)
        self.assertFalse(receipt['physical_acceptance_claimed'])
        self.assertEqual(ego.controls[-1]['brake'], 1.0)

    def test_ordinary_crossing_uses_source_bound_roadway_route(self):
        p = packet()
        p['roadway_route'] = [[-3, -2], [5, -2], [13, -2]]
        receipt, trace, _ = self.run_capture([[-3, -2], [5, -2], [13, -2]],
            case_id='testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__ordinary_crossing',
            map_packet=p)
        self.assertEqual(receipt['destination_entry_frame'], 3)
        observed = sys.modules['property_route'].analyze(p, trace, {'case_id': trace['case_id']})
        self.assertEqual(observed['traversed_property_ids'], [])

    def test_ordinary_crossing_rejects_property_connector_as_roadway(self):
        p = packet()
        p['roadway_route'] = [[-3, 5], [5, 5], [13, 5]]
        with self.assertRaisesRegex(ValueError, 'ordinary roadway route traverses'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]],
                case_id='testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__ordinary_crossing',
                map_packet=p)

    def test_no_destination_entry_rejects_and_brakes(self):
        ego = FakeEgo([[-3, 5]] * 20)
        world = FakeWorld(ego, list(range(1, 21)))
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'entry not observed'):
                capture.capture(world=world, ego=ego, map_packet=packet(), property_id='lot',
                                case_id='exact-case', purpose={'source': 'authored intent', 'value': 'avoid_red'},
                                actor_source={'source': 'registry', 'class': 'vehicle'},
                                signal_observer=signals, destination_street_id='street-B',
                                output=Path(td) / 'trace.json', ticks=20,
                                control_applier=lambda actor, command: actor.apply_control(command))
        self.assertEqual(ego.controls[-1]['brake'], 1.0)

    def test_source_and_frame_gaps_reject(self):
        with self.assertRaisesRegex(ValueError, 'source, identity, orientation'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]], signal_observer=lambda f, n: {'state': 'green'})
        with self.assertRaisesRegex(ValueError, 'frames must increase'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]], frames=[1, 1, 2])
        with self.assertRaisesRegex(ValueError, 'frames must increase consecutively'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]], frames=[1, 3, 4])

    def test_native_snapshot_clock_and_settings_readback(self):
        with self.assertRaisesRegex(ValueError, '20 Hz clock drift'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]],
                             times=[40 + i / 20 + (0.02 if i == 6 else 0)
                                    for i in range(20)])
        with self.assertRaisesRegex(ValueError, 'synchronous 20 Hz'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]], delta=0.1)
        _, trace, _ = self.run_capture([[-3, 5], [5, 5], [13, 5]])
        self.assertEqual(trace['ego'][0]['time_s'], 40)

    def test_saved_analysis_rejects_mid_route_phase_change_and_missing_frame(self):
        _, trace, _ = self.run_capture([[-3, 5], [5, 5], [13, 5]])
        analyze = sys.modules['property_route'].analyze
        observed = analyze(packet(), trace, {'case_id': 'exact-case'})
        self.assertTrue(observed['all_observation_conditions_present'])
        trace['approach_signal_history'][1]['state'] = 'green'
        observed = analyze(packet(), trace, {'case_id': 'exact-case'})
        self.assertFalse(observed['approach_red_alone_facing_ego'])
        self.assertFalse(observed['all_observation_conditions_present'])
        trace['approach_signal_history'].pop()
        with self.assertRaisesRegex(ValueError, 'cover every body frame'):
            analyze(packet(), trace, {'case_id': 'exact-case'})

    def test_unreviewed_destination_identity_rejects(self):
        with self.assertRaisesRegex(ValueError, 'street source join'):
            self.run_capture([[-3, 5], [5, 5], [13, 5]], destination_street_id='unknown')

    def test_four_original_camera_archives_and_frame_map(self):
        ego = FakeEgo([[-3, 5], [5, 5], [13, 5]] + [[13, 5]] * 17)
        world = FakeWorld(ego)
        sink = io.BytesIO()
        Image.new('RGB', (2, 2), (10, 20, 30)).save(sink, format='PNG')
        pixels = sink.getvalue()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt = capture.capture(world=world, ego=ego, map_packet=packet(), property_id='lot',
                                      case_id='exact-case', purpose={'source': 'original intent', 'value': 'avoid_red'},
                                      actor_source={'source': 'original registry', 'class': 'vehicle'},
                                      signal_observer=signals, destination_street_id='street-B',
                                      output=root / 'trace.json', ticks=20,
                                      control_applier=lambda actor, command: actor.apply_control(command),
                                      camera_observer=lambda frame, name: pixels, media_directory=root)
            media = receipt['media']
            self.assertEqual(len((root / 'frame-map.jsonl').read_text().splitlines()), 20)
            self.assertEqual(set(media['cameras']), set(capture.CAMERAS))
            for name in capture.CAMERAS:
                self.assertEqual(len(media['cameras'][name]['frames']), 20)
                with ZipFile(root / (name + '.zip')) as archive:
                    self.assertEqual(len(archive.namelist()), 20)
            self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_planned_900_frame_episode_continues_after_entry(self):
        ego = FakeEgo([[-3, 5], [5, 5], [13, 5]] + [[13, 5]] * 897)
        with tempfile.TemporaryDirectory() as td:
            receipt = capture.capture(world=FakeWorld(ego), ego=ego, map_packet=packet(),
                                      property_id='lot', case_id='exact-case',
                                      purpose={'source': 'original intent', 'value': 'avoid_red'},
                                      actor_source={'source': 'original registry', 'class': 'vehicle'},
                                      signal_observer=signals, destination_street_id='street-B',
                                      output=Path(td) / 'trace.json',
                                      control_applier=lambda actor, command: actor.apply_control(command))
            self.assertEqual(receipt['sample_count'], 900)
            self.assertEqual(receipt['destination_entry_frame'], 3)
            self.assertEqual(receipt['last_frame'], 900)

    def test_camera_failure_brakes_and_no_success_receipt(self):
        ego = FakeEgo([[-3, 5]] * 20)
        sink = io.BytesIO()
        Image.new('RGB', (2, 2)).save(sink, format='PNG')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'original PNG bytes'):
                capture.capture(world=FakeWorld(ego), ego=ego, map_packet=packet(),
                                property_id='lot', case_id='exact-case',
                                purpose={'source': 'original intent', 'value': 'avoid_red'},
                                actor_source={'source': 'original registry', 'class': 'vehicle'},
                                signal_observer=signals, destination_street_id='street-B',
                                output=Path(td) / 'trace.json', ticks=20,
                                control_applier=lambda actor, command: actor.apply_control(command),
                                camera_observer=lambda frame, name: None if name == 'destination' else sink.getvalue(),
                                media_directory=Path(td))
        self.assertEqual(ego.controls[-1]['brake'], 1.0)


if __name__ == '__main__':
    unittest.main()
