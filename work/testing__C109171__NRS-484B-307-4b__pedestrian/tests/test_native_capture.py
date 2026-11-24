import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CAMERAS, audit_frame_map, capture
from saved_measurement import ASSIGNMENT
from native_scene import SourceError
from saved_process import process


class Adapter:
    def __init__(self, rows, png, bad_camera=None, bad_frame=None):
        self.rows, self.png = rows, png
        self.bad_camera, self.bad_frame = bad_camera, bad_frame
        self.closed = False

    def start(self, site, case_id):
        self.site, self.case_id = site, case_id

    def read(self, frame):
        if self.bad_frame == frame:
            event = dict(self.rows[frame], frame=frame + 1)
        else:
            event = self.rows[frame]
        cameras = {name: {'frame': frame,
                          'png': self.png[name] if isinstance(self.png, dict) else self.png}
                   for name in CAMERAS}
        if self.bad_camera and frame == 1:
            cameras[self.bad_camera]['frame'] = 99
        return {'event': event, 'cameras': cameras}

    def close(self):
        self.closed = True


class NativeCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.refs = []
        def ref(name, value):
            p = self.root / name
            p.write_text(json.dumps(value), encoding='utf-8')
            return {'path': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        route = [[-2, 1], [-1, 1], [1, 1], [3, 1]]
        boundary = [[0, 0], [4, 0], [4, 4], [0, 4]]
        refs = [
            ref('map.json', {'route_id': 'crossing-1', 'pedestrian_route_xy': route,
                             'highway_boundary_xy': boundary}),
            ref('head.json', {'head_id': 'head-1', 'official': True,
                              'sole_green_arrow_aspect': 'green-left-arrow'}),
            ref('device.json', {'device_id': 'ped-1', 'governs_route_id': 'crossing-1'})]
        self.site = {'source_kind': 'native_original', 'cell_id': 'C109171', 'actor': 'pedestrian',
                     'original_sources': refs, 'map_source_path': 'map.json',
                     'vehicle_signal_source_path': 'head.json',
                     'pedestrian_device_source_path': 'device.json',
                     'official_vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
                     'pedestrian_route_id': 'crossing-1', 'pedestrian_device_governs_route': True,
                     'pedestrian_faces_vehicle_head': True,
                     'sole_green_arrow_aspect': 'green-left-arrow',
                     'pedestrian_route_xy': route, 'highway_boundary_xy': boundary}
        self.site_ref = ref('site.json', self.site)
        buf = io.BytesIO()
        Image.new('RGB', (4, 4), (1, 2, 3)).save(buf, format='PNG')
        self.png = buf.getvalue()

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, enter=False, walk=False):
        points = [-2, -1, 1 if enter else -0.5, 2 if enter else -0.5]
        return [{'frame': i, 'sim_time_seconds': i * 0.05,
                 'vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
                 'vehicle_head_lit_aspects': ['green-left-arrow'],
                 'pedestrian_facing_vehicle_head': True,
                 'pedestrian_device_indication': 'WALK' if walk and i >= 1 else 'DONT_WALK',
                 'pedestrian_xy': [x, 1]} for i, x in enumerate(points)]

    def run_case(self, suffix, enter, walk):
        adapter = Adapter(self.rows(enter, walk), self.png)
        result = capture(self.site, self.site_ref, self.root, adapter, ASSIGNMENT + '__' + suffix, 4)
        self.assertTrue(adapter.closed)
        self.assertEqual(result['frame_count'], 4)
        self.assertFalse(result['physical_acceptance'])
        audit = audit_frame_map(self.root, result['frame_map_ref'], result['events_ref'], 4)
        self.assertEqual(audit['camera_frames_audited'], 16)
        return result

    def test_four_exact_cases_and_reopen_all_cameras(self):
        for suffix, enter, walk in [('arrow_wait', False, False),
                                    ('arrow_early_entry', True, False),
                                    ('arrow_walk_entry', True, True),
                                    ('arrow_walk_wait', False, True)]:
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory() as sub:
                    # Each case owns a clean attempt; copy source packets without altering bytes.
                    target = Path(sub)
                    for src in self.root.glob('*.json'):
                        (target / src.name).write_bytes(src.read_bytes())
                    adapter = Adapter(self.rows(enter, walk), self.png)
                    result = capture(self.site, self.site_ref, target, adapter,
                                     ASSIGNMENT + '__' + suffix, 4)
                    self.assertTrue(adapter.closed)
                    self.assertEqual(result['measurement']['frame_count'], 4)
                    self.assertEqual(audit_frame_map(target, result['frame_map_ref'],
                                      result['events_ref'], 4)['camera_frames_audited'], 16)

    def test_reject_missing_or_drifted_callback_and_close(self):
        adapter = Adapter(self.rows(), self.png, bad_camera='approach')
        with self.assertRaisesRegex(SourceError, 'camera callback frame drift'):
            capture(self.site, self.site_ref, self.root, adapter, ASSIGNMENT + '__arrow_wait', 4)
        self.assertTrue(adapter.closed)

    def test_reject_event_drift_and_close(self):
        adapter = Adapter(self.rows(), self.png, bad_frame=1)
        with self.assertRaisesRegex(SourceError, 'original event frame drift'):
            capture(self.site, self.site_ref, self.root, adapter, ASSIGNMENT + '__arrow_wait', 4)
        self.assertTrue(adapter.closed)

    def test_reject_tampered_saved_pixel(self):
        result = self.run_case('arrow_wait', False, False)
        path = self.root / 'camera_png/0001_overview.png'
        path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(SourceError, 'camera source hash mismatch'):
            audit_frame_map(self.root, result['frame_map_ref'], result['events_ref'], 4)

    def test_saved_process_joins_entry_and_all_original_cameras_once(self):
        captured = self.run_case('arrow_walk_entry', True, True)
        output = self.root / 'processed' / 'receipt.json'
        result = process(self.root, self.site_ref, captured['events_ref'],
                         captured['frame_map_ref'],
                         ASSIGNMENT + '__arrow_walk_entry', output,
                         expected_frames=4, delivery_profile=False)
        self.assertEqual(result, json.loads(output.read_text()))
        self.assertEqual(result['measurement']['first_highway_entry']['frame'], 2)
        self.assertEqual(result['media_audit']['camera_frames_audited'], 16)
        self.assertEqual(result['statutory_permission'], 'unresolved')
        with self.assertRaisesRegex(SourceError, 'already exists'):
            process(self.root, self.site_ref, captured['events_ref'],
                    captured['frame_map_ref'], ASSIGNMENT + '__arrow_walk_entry',
                    output, expected_frames=4, delivery_profile=False)

    def test_saved_process_rejects_changed_camera_without_output(self):
        captured = self.run_case('arrow_wait', False, False)
        (self.root / 'camera_png/0001_overview.png').write_bytes(b'changed')
        output = self.root / 'processed.json'
        with self.assertRaisesRegex(SourceError, 'camera source hash mismatch'):
            process(self.root, self.site_ref, captured['events_ref'],
                    captured['frame_map_ref'], ASSIGNMENT + '__arrow_wait',
                    output, expected_frames=4, delivery_profile=False)
        self.assertFalse(output.exists())

    def test_saved_process_requires_pinned_delivery_dimensions_by_default(self):
        captured = self.run_case('arrow_wait', False, False)
        output = self.root / 'production_receipt.json'
        with self.assertRaisesRegex(SourceError, 'dimensions differ from pinned profile'):
            process(self.root, self.site_ref, captured['events_ref'],
                    captured['frame_map_ref'], ASSIGNMENT + '__arrow_wait',
                    output, expected_frames=4)
        self.assertFalse(output.exists())

    def test_saved_process_writes_profile_verified_receipt(self):
        from delivery_media import PROFILE_SIZES
        originals = {}
        for name, size in PROFILE_SIZES.items():
            stream = io.BytesIO()
            Image.new('RGB', size, (1, 2, 3)).save(stream, format='PNG')
            originals[name] = stream.getvalue()
        captured = capture(self.site, self.site_ref, self.root,
                           Adapter(self.rows(), originals),
                           ASSIGNMENT + '__arrow_wait', 4)
        output = self.root / 'verified_receipt.json'
        receipt = process(self.root, self.site_ref, captured['events_ref'],
                          captured['frame_map_ref'], ASSIGNMENT + '__arrow_wait',
                          output, expected_frames=4)
        self.assertTrue(receipt['delivery_media_audit']['pinned_dimensions_verified'])
        self.assertEqual(receipt['delivery_media_audit']['decoded_source_frames'], 16)
        self.assertEqual(json.loads(output.read_text()), receipt)

    def test_reject_diagnostic_site(self):
        site = dict(self.site, source_kind='diagnostic')
        adapter = Adapter(self.rows(), self.png)
        with self.assertRaisesRegex(SourceError, 'diagnostic'):
            capture(site, self.site_ref, self.root, adapter, ASSIGNMENT + '__arrow_wait', 4)

    def test_full_duration_four_camera_join(self):
        original = self.rows()
        rows = []
        for i in range(900):
            row = dict(original[min(i, 3)])
            row['frame'] = i
            row['sim_time_seconds'] = i * 0.05
            rows.append(row)
        adapter = Adapter(rows, self.png)
        result = capture(self.site, self.site_ref, self.root, adapter,
                         ASSIGNMENT + '__arrow_wait')
        self.assertTrue(adapter.closed)
        self.assertEqual(result['frame_count'], 900)
        self.assertEqual(audit_frame_map(self.root, result['frame_map_ref'],
                                        result['events_ref'])['camera_frames_audited'], 3600)


if __name__ == '__main__':
    unittest.main()
