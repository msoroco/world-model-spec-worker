import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import capture
from reviewed_source import FIELDS, verify


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Adapter:
    native_attested = True

    def __init__(self, source_hashes):
        self.source_hashes = source_hashes
        self.index = -1
        self.destroyed = []
        self.restored = False

    def mark_loading_location(self, *args):
        pass

    def spawn_bus(self, *args):
        return 'bus'

    def spawn_traffic(self, *args):
        return 'traffic'

    def set_bus_entry_and_halt(self, *args):
        pass

    def set_loading_activity(self, *args):
        pass

    def set_traffic_route(self, *args):
        pass

    def tick(self, actors):
        self.index += 1
        return {'frame': 100 + self.index, 'time_s': self.index / 20}

    def read_bus_row(self, frame, actors):
        row = {'origin': 'native_world_snapshot', 'original_frame': frame,
               'time_s': self.index / 20, 'bus_id': 'bus', 'traffic_id': 'traffic',
               'activity': 'passenger_loading', 'bus_speed_mps': 0,
               'traffic_speed_mps': 3, 'loading_active': True,
               'right_front_wheel_xy': [5, .4472],
               'wheel_position_uncertainty_m': .001, 'bus_curb_angle_deg': 0}
        for name in ('right_front_wheel', 'curb_geometry', 'location_designation',
                     'loading_activity'):
            row[name + '_source_sha256'] = self.source_hashes[name]
        for name in ('frame', 'bus_motion', 'traffic_motion'):
            row[name + '_source_sha256'] = 'a' * 64
        return row

    def read_cameras(self, frame, actors):
        return {name: {'frame': frame, 'time_s': self.index / 20,
                       'png': b'\x89PNG\r\n\x1a\nsynthetic pixels'}
                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}

    def brake(self):
        pass

    def destroy(self, actor):
        self.destroyed.append(actor)

    def restore(self):
        self.restored = True


class NativeCaptureTests(unittest.TestCase):
    def test_source_sealed_positive_and_wrong_attestation_rejection(self):
        scratch = ROOT.parents[1] / '.runtime-work/c149470/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            base = Path(folder)
            construction = json.loads((ROOT / 'construction-diagnostic-bus_stop_below.json').read_text())
            scene = json.loads(next(item['content'] for item in construction['files']
                                    if item['path'] == 'scene.json'))
            scene['source_kind'] = 'original_reviewed_site'
            bindings = {}
            for name in FIELDS:
                source = base / (name + '.txt')
                source.write_text('reviewed original fixture source: ' + name + '\n')
                digest = sha(source)
                scene[name + '_source_sha256'] = digest
                bindings[name] = {'path': source.name, 'sha256': digest,
                                  'citation': 'fixture source ' + name, 'reviewer': 'unit test'}
            packet = base / 'site.json'
            packet.write_text(json.dumps({'format': 'c149470-reviewed-site-v1',
                                          'review_status': 'reviewed', 'reviewer': 'unit test',
                                          'scene': scene, 'source_bindings': bindings}) + '\n')
            adapter = Adapter({name: scene[name + '_source_sha256'] for name in FIELDS})
            destination = base / 'attempt'

            def encode(command, **kwargs):
                Path(command[-1]).write_bytes(b'MOCK ONLY VIDEO')

            with patch('native_capture.subprocess.run', side_effect=encode):
                receipt = capture(adapter, packet, 'bus_stop_below', destination)
            self.assertEqual(receipt['source_kind'], 'original_native_capture')
            self.assertEqual(len((destination / 'original-bus-frames.jsonl').read_text().splitlines()), 900)
            self.assertEqual(set(receipt['cameras']), {'overview', 'approach', 'reference_corner', 'driver_reference'})
            self.assertEqual(len((destination / 'camera-frame-map.jsonl').read_text().splitlines()), 900)
            self.assertEqual(set(receipt['camera_archives']),
                             {'overview', 'approach', 'reference_corner', 'driver_reference'})
            self.assertEqual(adapter.destroyed, ['traffic', 'bus'])
            self.assertTrue(adapter.restored)
            reject = Adapter(adapter.source_hashes)
            reject.native_attested = False
            with self.assertRaisesRegex(ValueError, 'attested original'):
                capture(reject, packet, 'bus_stop_below', base / 'rejected')
            self.assertFalse((base / 'rejected').exists())
            fallback = json.loads(packet.read_text())
            fallback['candidate_id'] = 'fallback1'
            fallback['scene']['primary_bus_route_xy'] = json.loads(json.dumps(scene['bus_route_xy']))
            fallback['scene']['bus_route_xy'][0][0] -= 2.0
            fallback_path = base / 'fallback-site.json'
            fallback_path.write_text(json.dumps(fallback) + '\n')
            self.assertEqual(verify(fallback_path, 'bus_stop_below', 'fallback1')['case_name'],
                             'bus_stop_below')
            with self.assertRaisesRegex(ValueError, 'candidate identity'):
                verify(fallback_path, 'bus_stop_below', 'primary')
            fallback['scene']['bus_route_xy'][0][0] += 1.0
            fallback_path.write_text(json.dumps(fallback) + '\n')
            with self.assertRaisesRegex(ValueError, 'fallback does not preserve'):
                verify(fallback_path, 'bus_stop_below', 'fallback1')
