import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_capture', ROOT / 'native_capture.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
SPEC = importlib.util.spec_from_file_location('delivery_audit_for_native_test', ROOT / 'delivery_audit.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def source(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}


def site(root):
    return {'native_map_source': source(root, 'native/map.json', {'original_opendrive_hash': 'fixture-only'}),
            'highway_review_source': source(root, 'review/highway.json', {'public_highway': 'fixture-only'}),
            'public_highway_confirmed': True,
            'lanes': [
                {'id': 'center', 'road_id': 42, 'center_turn_lane': True, 'exclusive_turn_use': True,
                 'permitted_turn_directions': ['negative', 'positive'], 'centreline_xy_m': [[0, 0], [100, 0]]},
                {'id': 'east', 'road_id': 42, 'receiving_through': True, 'centreline_xy_m': [[0, -3], [100, -3]]},
                {'id': 'west', 'road_id': 42, 'opposing_through': True, 'centreline_xy_m': [[100, 3], [0, 3]]}],
            'entry_maneuver': 'left_turn_onto_highway', 'entry_target_lane_id': 'center', 'merge_target_lane_id': 'east'}


def readings(root, merge=True):
    lanes = ['approach', 'center', 'center', 'east' if merge else 'center']
    data = [{'frame': 100 + i, 'elapsed_seconds': i / 20, 'body_centre_xy_m': [i * 5.0, 0.0],
             'lane_id': lane, 'approach_lane': i == 0,
             'left_turn_onto_highway_complete': i == 1,
             'merged_into_through_lane': merge and i == 3,
             'camera_sources': {view: 'camera/' + view + '/%06d.png' % (100 + i) for view in CAPTURE.VIEWS}}
            for i, lane in enumerate(lanes)]
    for row in data:
        for relative in row['camera_sources'].values():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('diagnostic-' + relative).encode())
    return data


class NativeCaptureTests(unittest.TestCase):
    def test_original_capture_joins_existing_saved_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = readings(root)
            receipt = CAPTURE.capture_original(root, 'exact-case', site(root), data.__getitem__, len(data), first_frame=100)
            outcome = AUDIT.audit_saved_delivery(root, receipt)
            self.assertEqual(outcome['verified_frame_count'], 4)
            self.assertTrue(outcome['measured']['merge_observed'])
            self.assertAlmostEqual(outcome['measured']['distance_ft'], 10 * 3.280839895013123)
            self.assertIsNone(outcome['physical_acceptance'])
            (root / data[2]['camera_sources']['approach']).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'camera source hash mismatch'):
                AUDIT.audit_saved_delivery(root, receipt)

    def test_censored_case_preserves_unknown_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = readings(root, False)
            receipt = CAPTURE.capture_original(root, 'no-merge', site(root), data.__getitem__, len(data))
            self.assertTrue(AUDIT.audit_saved_delivery(root, receipt)['measured']['censored'])

    def test_rejects_frame_gap_time_drift_camera_and_lane(self):
        for change, error in [
            (lambda d: d[2].update(frame=104), 'noncontiguous'),
            (lambda d: d[2].update(elapsed_seconds=0.2), '20 Hz'),
            (lambda d: d[2]['camera_sources'].pop('approach'), 'four-camera'),
            (lambda d: d[2].update(lane_id='unknown'), 'lane identity'),
            (lambda d: d[1].update(left_turn_onto_highway_complete=False), 'exactly one')]:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = readings(root)
                change(data)
                with self.assertRaisesRegex(ValueError, error):
                    CAPTURE.capture_original(root, 'exact-case', site(root), data.__getitem__, len(data))

    def test_rejects_map_source_drift_and_duplicate_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = site(root)
            (root / 'native/map.json').write_text('{}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                CAPTURE.capture_original(root, 'exact-case', packet, readings(root).__getitem__, 4)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = site(root)
            data = readings(root)
            CAPTURE.capture_original(root, 'exact-case', packet, data.__getitem__, 4)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                CAPTURE.capture_original(root, 'exact-case', packet, data.__getitem__, 4)

    def test_rejects_site_without_highway_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = site(root)
            packet['public_highway_confirmed'] = False
            with self.assertRaisesRegex(ValueError, 'public-highway'):
                CAPTURE.capture_original(root, 'exact-case', packet, readings(root).__getitem__, 4)


if __name__ == '__main__':
    unittest.main()
