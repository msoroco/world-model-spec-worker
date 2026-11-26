"""Structural saved-source join tests; synthetic bytes prove no physical facts."""
import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from finalize_original import SOURCES, inspect, sha
from seal_review import seal
from audit_original import decode
import subprocess

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def fixture(folder):
    folder = Path(folder)
    config = json.loads(next(item['content'] for item in
        json.loads((PACKAGE / 'native-draft/probe_a/construction.json').read_text())['files']
        if item['path'] == 'config.json'))
    write(folder / 'config.json', config)
    (folder / 'yellow-road.xodr').write_bytes((PACKAGE / 'native/yellow-road.xodr').read_bytes())
    (folder / 'road.xodr').write_text('synthetic CPU road readback\n')
    write(folder / 'sign-authority-pending.json', {'legal_verdict': None})
    review = {'source_kind': 'synthetic_cpu_fixture',
              'source_basis': 'synthetic shape test only', 'legal_verdict': None}
    write(folder / 'taxicab-review.json', {**review, 'observed_taxicab': True})
    write(folder / 'sign-review.json', {**review, 'observed_curb_color': 'yellow',
                                       'posted_hours_start': '09:00', 'posted_hours_end': '17:00'})
    write(folder / 'passenger-purpose-review.json', {**review,
                                                     'observed_purpose': 'waiting_for_passengers'})
    write(folder / 'ordinary-rules-review.json', {**review, 'review_status': 'unresolved'})
    for view in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (folder / (view + '.mkv')).write_bytes(b'synthetic CPU video placeholder')
    start = datetime.fromisoformat(config['civil_start_local'])
    native, frame_map, trace = [], [], []
    for index in range(600):
        frame, time_s = 1000 + index, (index + 1) / 20
        cameras = {name: frame for name in
                   ('overview', 'approach', 'reference_corner', 'driver_reference')}
        native.append({'video_frame': index, 'native_frame': frame, 'time_s': time_s,
                       'source_kind': 'synthetic_cpu_fixture',
                       'civil_time_local': (start + timedelta(seconds=time_s)).isoformat(timespec='milliseconds'),
                       'taxi_actor_id': 1, 'passenger_proxy_id': 2,
                       'taxi_body_vertices_xyz_m': [[x, y, z] for x in (4.5, 6.0)
                                                    for y in (9.0, 11.0) for z in (0.0, 1.5)],
                       'taxi_velocity_xyz_mps': [0, 0, 0], 'source_cameras': cameras})
        frame_map.append({'video_frame': index, 'carla_frame': frame,
                          'time_s': time_s, 'camera_native_frames': cameras})
        trace.append({'frame': frame, 'time_s': time_s})
    for name, rows in [('yellow-zone-native.jsonl', native),
                       ('video_frames.jsonl', frame_map), ('trace.jsonl', trace)]:
        (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    manifest = folder / 'source-manifest.json'
    write(manifest, {'source_kind': 'synthetic_cpu_fixture',
                     'sha256': {name: sha(folder / name) for name in SOURCES}})
    return manifest


class SourceJoin(unittest.TestCase):
    def test_full_video_decoder_and_profile_rejection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as tmp:
            video = Path(tmp) / 'diagnostic.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                '-i', 'color=c=black:s=160x90:r=20', '-frames:v', '600',
                '-an', '-c:v', 'ffv1', str(video)], check=True, timeout=120)
            self.assertEqual(decode(video, (160, 90))['frames'], 600)
            with self.assertRaisesRegex(ValueError, 'Camera decode profile differs'):
                decode(video, (160, 91))

    def test_positive_and_changed_or_missing_sources(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as tmp:
            folder = Path(tmp)
            manifest = fixture(folder)
            measured = inspect(folder, manifest, 'synthetic_cpu_fixture')
            self.assertEqual(measured['frames'], 600)
            self.assertEqual(measured['posted_active_stopped_frames'], 600)
            self.assertEqual(measured['yellow_zone_body_frames'], 600)
            self.assertFalse(measured['original_native_observed'])
            with self.assertRaisesRegex(ValueError, 'Source kind differs'):
                inspect(folder, manifest)
            video = folder / 'overview.mkv'
            video.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed original source'):
                inspect(folder, manifest, 'synthetic_cpu_fixture')
            video.write_bytes(b'synthetic CPU video placeholder')
            purpose = folder / 'passenger-purpose-review.json'
            purpose.unlink()
            with self.assertRaisesRegex(ValueError, 'changed original source'):
                inspect(folder, manifest, 'synthetic_cpu_fixture')

    def test_synthetic_reviews_cannot_be_sealed_as_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as tmp:
            folder = Path(tmp)
            fixture(folder).unlink()
            with self.assertRaisesRegex(ValueError, 'Independent original review'):
                seal(folder)


if __name__ == '__main__':
    unittest.main()
