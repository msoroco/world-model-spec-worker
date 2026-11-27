import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import test_source_packet as packet_support
import red_curb
import source_packet


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_capture', ROOT / 'native_capture.py')
native_capture = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native_capture
spec.loader.exec_module(native_capture)


class FakePipeline:
    def __init__(self, client, vehicle, output, case_id, required_observations):
        self.closed = False

    def capture(self, frame, elapsed):
        return {'frame': frame, 'time_s': elapsed}

    def close(self, confirmed):
        self.closed = True


class FakeFrameMap:
    def __init__(self, path):
        self.path = Path(path)
        self.count = 0

    def __enter__(self):
        return self

    def append(self, frame, elapsed):
        self.count += 1

    def __exit__(self, *args):
        self.path.write_text(str(self.count) + '\n')


class FakeAdapter:
    def __init__(self, scene, case, *, lose_camera=False, restore=True):
        self.scene, self.case = scene, case
        self.index = -1
        self.destroyed = []
        self.lose_camera = lose_camera
        self.restore = restore
        self.aborted = False

    def mark_red_curb(self, segment):
        self.segment = segment

    def set_sign(self, sign, text):
        self.sign = sign

    def spawn_vehicle(self, kind, position):
        return 'ego'

    def set_parking_route(self, vehicle, route):
        self.route = route

    def set_halt_activity(self, vehicle, activity, purpose):
        self.activity = activity

    def pipeline_client(self):
        return self

    def start_cameras(self, output, plan):
        self.output = Path(output)
        return {name: True for name in source_packet.CAMERAS}

    def advance_halt(self, built, index, hz):
        self.index = index

    def tick_world(self):
        return 1000 + self.index, self.index / 20

    def camera_frame_ids(self, frame):
        return {name: frame for name in source_packet.CAMERAS
                if not self.lose_camera or name != 'approach'}

    def sample_halt_event(self, built, frame):
        if self.index not in (0, self.case.duration_s * 20):
            return None
        row = {'vehicle_id': 'ego', 'original_frame': frame,
               'original_time_s': self.index / 20, 'vehicle_speed_mps': 0,
               'halted': True, 'activity': self.case.activity,
               'purpose': self.case.purpose, 'attended': False,
               'engine_running': False,
               'red_curb_source_sha256': self.scene['red_curb_source_sha256']}
        for field in ('event', 'vehicle_motion', 'curb_position', 'activity',
                      'attendance', 'engine', 'sign', 'purpose'):
            row[field + '_source_sha256'] = 'a' * 64
        return row

    def finish_cameras(self):
        result = {}
        for name in source_packet.CAMERAS:
            path = self.output / (name + '.mkv')
            path.write_bytes(b'fake-video-source')
            result[name] = path
        return result

    def abort_cameras(self):
        self.aborted = True

    def destroy(self, actor):
        self.destroyed.append(actor)

    def restore_world(self):
        return self.restore


class CaptureTests(unittest.TestCase):
    def run_capture(self, case, **adapter_kwargs):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            packet_path, packet = packet_support.ReviewedPacketTests().make_packet(Path(tmp), case)
            adapter = FakeAdapter(packet['scene'], case, **adapter_kwargs)
            seals = []
            def seal(*args, **kwargs):
                seals.append(kwargs)
            output = Path(tmp) / 'attempt'
            result = native_capture.acquire(
                adapter, packet_path, packet['case_id'], output,
                pipeline_factory=FakePipeline, seal_factory=seal,
                frame_map_factory=FakeFrameMap,
                frame_count=case.duration_s * 20 + 1)
            self.assertEqual(result['frames'], case.duration_s * 20 + 1)
            self.assertEqual(result['measurement']['original_duration_s'], case.duration_s)
            self.assertFalse(result['physical_visibility_verified'])
            self.assertEqual(adapter.destroyed, ['ego'])
            self.assertEqual(seals[0]['frames'], result['frames'])
            self.assertTrue((output / 'original-red-curb-events.jsonl').is_file())

    def test_original_short_stop_and_mail_interval(self):
        for case in (red_curb.CASES[0], next(item for item in red_curb.CASES
                                               if item.name == 'mail_stop')):
            with self.subTest(case=case.name):
                self.run_capture(case)

    def test_missing_original_camera_rejected_with_cleanup(self):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        case = next(item for item in red_curb.CASES if item.name == 'mail_stop')
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            packet_path, packet = packet_support.ReviewedPacketTests().make_packet(Path(tmp), case)
            adapter = FakeAdapter(packet['scene'], case, lose_camera=True)
            with self.assertRaisesRegex(ValueError, 'camera frames do not join'):
                native_capture.acquire(
                    adapter, packet_path, packet['case_id'], Path(tmp) / 'attempt',
                    pipeline_factory=FakePipeline, seal_factory=lambda *a, **k: None,
                    frame_map_factory=FakeFrameMap, frame_count=401)
            self.assertTrue(adapter.aborted)
            self.assertEqual(adapter.destroyed, ['ego'])

    def test_full_interval_required(self):
        case = next(item for item in red_curb.CASES if item.name == 'tour_bus_1801')
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            packet_path, packet = packet_support.ReviewedPacketTests().make_packet(Path(tmp), case)
            adapter = FakeAdapter(packet['scene'], case)
            with self.assertRaisesRegex(ValueError, 'full original halt interval'):
                native_capture.acquire(
                    adapter, packet_path, packet['case_id'], Path(tmp) / 'attempt',
                    pipeline_factory=FakePipeline, seal_factory=lambda *a, **k: None,
                    frame_map_factory=FakeFrameMap, frame_count=900)


if __name__ == '__main__':
    unittest.main()
