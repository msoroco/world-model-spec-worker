"""Independent original-attempt receipt validation with source-shaped fake bytes."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import ASSIGNMENT, CAMERAS, audit
from reviewed_source import FIELDS
from test_one_way_direction import probe, rows, scene


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = probe.CASES[0]
        self.case_id = ASSIGNMENT + '__' + self.case.name
        self.scene = scene(self.case)
        bindings = {}
        for field in FIELDS:
            path = self.root / (field + '.txt')
            path.write_text('fixture ' + field)
            digest = sha(path)
            self.scene[field + '_source_sha256'] = digest
            bindings[field] = {'path': path.name, 'sha256': digest,
                               'citation': 'test fixture', 'reviewer': 'test'}
        site = {'format': 'c147311-reviewed-site-v1', 'review_status': 'reviewed',
                'reviewer': 'test fixture', 'diagnostic_fixture': False,
                'scene': self.scene, 'source_bindings': bindings}
        (self.root / 'site.json').write_text(json.dumps(site))
        samples = rows(self.case, self.scene)
        for row in samples:
            for field in ('driver_control', 'lane_inventory', 'one_way_designation',
                          'sign_authority', 'sign_message', 'sign_orientation',
                          'sign_governance'):
                row[field + '_source_sha256'] = self.scene[field + '_source_sha256']
        (self.root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in samples))
        frame_map = {'source_kind': 'original_native_frame_map', 'case_id': self.case_id,
                     'frames': [{'frame': i, 'native_frame': i, 'time_s': i / 20,
                                 'camera_frames': {name: i for name in CAMERAS}}
                                for i in range(900)]}
        (self.root / 'frame-map.json').write_text(json.dumps(frame_map))
        for name in CAMERAS:
            (self.root / (name + '.mkv')).write_bytes(b'diagnostic test bytes')
        def ref(name):
            return {'path': name, 'sha256': sha(self.root / name)}
        refs = {'site_ref': ref('site.json'), 'frame_map_ref': ref('frame-map.json'),
                'trace_ref': ref('trace.jsonl'),
                'video_refs': {name: ref(name + '.mkv') for name in CAMERAS}}
        sources = {item['path']: item['sha256'] for item in
                   [refs['site_ref'], refs['frame_map_ref'], refs['trace_ref'],
                    *refs['video_refs'].values()]}
        seal = {'source_kind': 'original_native_capture_seal', 'case_id': self.case_id,
                'attempt_id': 'test-attempt', 'recording_id': 'test-recording',
                'sources': sources}
        (self.root / 'seal.json').write_text(json.dumps(seal))
        self.receipt = {'case_id': self.case_id, 'source_kind': 'original_native_attempt',
                        'diagnostic_fixture': False, 'native_process_exit_code': 0,
                        'owner_released': True, 'attempt_id': 'test-attempt',
                        'recording_id': 'test-recording',
                        'capture_seal_ref': ref('seal.json'), **refs}
        self.probe = lambda path: {'nb_read_frames': '900', 'r_frame_rate': '20/1',
                                   'width': 1280, 'height': 720}

    def test_positive_receipt_and_negative_tamper(self):
        result = audit(self.root, self.receipt, self.probe)
        self.assertEqual(result['frames_checked'], 900)
        self.assertEqual(result['actual_direction'], 'designated')
        self.assertEqual(result['legal_judgment'], 'unresolved')
        (self.root / 'trace.jsonl').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'sealed original source changed'):
            audit(self.root, self.receipt, self.probe)

    def test_rejects_diagnostic_or_camera_drop(self):
        self.receipt['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'successful released original'):
            audit(self.root, self.receipt, self.probe)
        self.receipt['diagnostic_fixture'] = False
        self.receipt['video_refs'].pop('overview')
        with self.assertRaisesRegex(ValueError, 'sealed original source inventory differs|four original camera'):
            audit(self.root, self.receipt, self.probe)
