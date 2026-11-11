import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import audit_attempt, CAMERAS, SOURCES
from right_half_measurement import measure
from test_right_half_measurement import row
from hashlib import sha256


CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_east'


def fixture(root):
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': CASE, 'law_id': 'NRS-484B-200-1',
        'cell_id': 'C125714', 'actor': 'motor_vehicle_driver'}))
    content = {
        'video_frames.jsonl': [{'video_frame': i, 'carla_frame': i,
                                'time_s': i*.05} for i in range(2)],
        'trace.jsonl': [{'frame': i, 'time_s': i*.05} for i in range(2)],
        'directed_roadway_footprints.jsonl': [
            row(i, 1, [.2, .2, 1.8, 1.8]) for i in range(2)],
    }
    for name, entries in content.items():
        (root / name).write_text(''.join(json.dumps(item)+'\n' for item in entries))
    for camera in CAMERAS:
        (root / (camera+'.mkv')).write_bytes(b'fixture-camera')
    hashes = {name: sha256((root/name).read_bytes()).hexdigest() for name in SOURCES}
    report = {'case_id': CASE, 'measurements': {'right_half_occupancy': {
        'sources': hashes, 'value': measure(root / 'directed_roadway_footprints.jsonl')}}}
    return report


class DeliveryAuditTests(unittest.TestCase):
    def test_source_bound_positive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            receipt = audit_attempt(root, report, decoder=lambda _p, n, **_kw: {'frames': n})
            self.assertEqual(receipt['frame_count'], 2)
            self.assertEqual(len(receipt['camera_decodes']), 4)
            self.assertTrue(receipt['measurement_recomputed'])
            self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_missing_and_stale_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            (root / 'directed_roadway_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original audit source'):
                audit_attempt(root, report, decoder=lambda _p, n, **_kw: {'frames': n})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            path = root / 'trace.jsonl'
            path.write_text(path.read_text() + '{}\n')
            with self.assertRaisesRegex(ValueError, 'source hashes differ'):
                audit_attempt(root, report, decoder=lambda _p, n, **_kw: {'frames': n})

    def test_decode_count_and_measurement_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = fixture(root)
            with self.assertRaisesRegex(ValueError, 'camera frame count differs'):
                audit_attempt(root, report, decoder=lambda _p, n, **_kw: {'frames': n-1})
            report['measurements']['right_half_occupancy']['value']['minimum_body_right_offset_m'] = -99
            with self.assertRaisesRegex(ValueError, 'measurement differs'):
                audit_attempt(root, report, decoder=lambda _p, n, **_kw: {'frames': n})


if __name__ == '__main__':
    unittest.main()
