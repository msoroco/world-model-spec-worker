"""Fail-closed structural checks for original taxi source joins."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from finalize_original import finalize, REVIEW_FILES, SOURCE_FILES

ROOT = Path(__file__).resolve().parents[3] / '.runtime-work'


class OriginalSourceGate(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.attempt = Path(self.temporary.name)
        self.manifest = self.attempt / 'review-manifest.json'

    def write_manifest(self, payload):
        self.manifest.write_text(json.dumps(payload) + '\n')

    def test_request_cannot_be_promoted(self):
        self.write_manifest({'source_kind': 'authored_native_request',
                             'sha256': {}})
        with self.assertRaisesRegex(ValueError, 'Original-source manifest'):
            finalize(self.attempt, self.manifest)

    def test_exact_source_set_required(self):
        self.write_manifest({'source_kind': 'original_native',
                             'sha256': {'native-rows.jsonl': '0' * 64}})
        with self.assertRaisesRegex(ValueError, 'Exact Native'):
            finalize(self.attempt, self.manifest)

    def test_missing_and_changed_sources_rejected(self):
        names = REVIEW_FILES + SOURCE_FILES
        hashes = {name: '0' * 64 for name in names}
        self.write_manifest({'source_kind': 'original_native',
                             'sha256': hashes})
        with self.assertRaisesRegex(ValueError, 'Original source missing'):
            finalize(self.attempt, self.manifest)
        (self.attempt / names[0]).write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'Original source hash differs'):
            finalize(self.attempt, self.manifest)
        hashes[names[0]] = hashlib.sha256((self.attempt / names[0]).read_bytes()).hexdigest()
        self.write_manifest({'source_kind': 'original_native',
                             'sha256': hashes})
        with self.assertRaisesRegex(ValueError, 'Original source missing'):
            finalize(self.attempt, self.manifest)

    def test_legal_verdict_rejected(self):
        self.write_manifest({'source_kind': 'original_native',
                             'legal_verdict': 'compliant', 'sha256': {}})
        with self.assertRaisesRegex(ValueError, 'Legal verdict'):
            finalize(self.attempt, self.manifest)

    def test_source_join_shape_and_missing_observation(self):
        native, frames, observed = [], [], []
        for index in range(600):
            frame = index + 1
            time_s = (index + 1) / 20
            camera_frames = {view: frame for view in (
                'overview', 'approach', 'curb_reference', 'driver_reference')}
            native.append({'video_frame': index, 'native_frame': frame,
                           'time_s': time_s, 'taxi_actor_id': 1,
                           'participant_actor_id': 2,
                           'source_cameras': camera_frames})
            frames.append({'video_frame': index, 'native_frame': frame,
                           'time_s': time_s,
                           'camera_native_frames': camera_frames})
            observed.append({'video_frame': index, 'native_frame': frame,
                             'time_s': time_s, 'observed_taxi_identity': True,
                             'observed_stand_location': 'outside_designated_stand',
                             'observed_speed_mps': .02,
                             'observed_door_open': 160 <= index < 400,
                             'observed_occupant_count': 2 if index < 400 else 3,
                             'observed_activity': 'passenger_loading'
                             if 160 <= index < 400 else 'no_activity'})
        for name, rows in [('native-rows.jsonl', native),
                           ('video_frames.jsonl', frames),
                           ('observed-activity.jsonl', observed)]:
            (self.attempt / name).write_text(''.join(json.dumps(row) + '\n'
                                                       for row in rows))
        for name in REVIEW_FILES:
            (self.attempt / name).write_text(json.dumps({
                'source_kind': 'original_native', 'review_status': 'verified',
                'source_basis': 'synthetic shape fixture only',
                'legal_verdict': None}) + '\n')
        for name in SOURCE_FILES:
            if name.endswith('.mkv'):
                (self.attempt / name).write_bytes(b'synthetic-shape-only')
        names = REVIEW_FILES + SOURCE_FILES
        hashes = {name: hashlib.sha256((self.attempt / name).read_bytes()).hexdigest()
                  for name in names}
        self.write_manifest({'source_kind': 'original_native',
                             'synthetic_cpu_fixture': True,
                             'legal_verdict': None, 'sha256': hashes})
        result = finalize(self.attempt, self.manifest)
        self.assertEqual(result['requested_activity'], 'passenger_loading')
        self.assertEqual(result['active_frames'], 240)
        self.assertFalse(result['original_native_observed'])
        self.assertEqual(result['source_kind'], 'synthetic_cpu_fixture')
        observed[300].pop('observed_activity')
        (self.attempt / 'observed-activity.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in observed))
        hashes['observed-activity.jsonl'] = hashlib.sha256(
            (self.attempt / 'observed-activity.jsonl').read_bytes()).hexdigest()
        self.write_manifest({'source_kind': 'original_native',
                             'synthetic_cpu_fixture': True,
                             'legal_verdict': None, 'sha256': hashes})
        with self.assertRaisesRegex(ValueError, 'Loading activity source'):
            finalize(self.attempt, self.manifest)


if __name__ == '__main__':
    unittest.main()
