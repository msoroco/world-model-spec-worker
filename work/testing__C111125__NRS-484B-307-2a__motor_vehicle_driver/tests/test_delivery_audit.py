import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_saved_attempt import packet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('delivery_audit', ROOT / 'delivery_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def hashed(path):
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build(base):
    p = packet(base, 'green_pedestrian_present')
    other_devices = base / 'other-devices.json'
    other_devices.write_text(json.dumps({'survey_status': 'review_required',
                                         'devices': []}), encoding='utf-8')
    pedestrian_context = base / 'reviewed-pedestrian-context.json'
    pedestrian_context.write_text(json.dumps({'participant_id': 'pedestrian-2',
                                              'lawful_presence': None}), encoding='utf-8')
    context_path = base / 'context.json'
    context_path.write_text(json.dumps({
        'official_head_id': 'head-7', 'ego_approach_id': 'north',
        'other_devices_ref': hashed(other_devices),
        'participant_context_refs': {'pedestrian-2': hashed(pedestrian_context)},
    }), encoding='utf-8')
    p['context_ref'] = hashed(context_path)
    views = module.VIEWS
    profile_path = base / 'camera-profile.json'
    profile_path.write_text(json.dumps({'fps': 20,
                                        'views': {v: [16, 16] for v in views}}),
                            encoding='utf-8')
    p['camera_profile_ref'] = hashed(profile_path)
    p['camera_profile_sha256'] = p['camera_profile_ref']['sha256']
    frame_map = [{'index': i, 'frame': i + 1,
                  'camera_frame_ids': {v: i + 1 for v in views}}
                 for i in range(3)]
    frame_path = base / 'frame-map.json'
    frame_path.write_text(json.dumps(frame_map), encoding='utf-8')
    p['frame_map_ref'] = hashed(frame_path)
    media = {}
    for view in views:
        target = base / (view + '.mkv')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi',
                        '-i', 'color=c=blue:s=16x16:r=20', '-frames:v', '3',
                        '-c:v', 'ffv1', str(target)], check=True)
        media[view] = hashed(target)
    p['camera_media_refs'] = media
    return p


class DeliveryAuditTests(unittest.TestCase):
    def test_complete_four_camera_source_join(self):
        with tempfile.TemporaryDirectory() as d:
            p = build(Path(d))
            receipt = module.audit_saved_delivery(
                p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
            self.assertTrue(receipt['software_audit_passed'])
            self.assertFalse(receipt['physical_acceptance_claimed'])
            self.assertEqual(set(receipt['camera_media']), set(module.VIEWS))
            self.assertTrue(all(v['full_decode'] for v in receipt['camera_media'].values()))

    def test_rejects_original_map_drift_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            rows = json.loads((base / 'frame-map.json').read_text())
            rows[1]['camera_frame_ids']['approach'] = 99
            (base / 'frame-map.json').write_text(json.dumps(rows))
            p['frame_map_ref'] = hashed(base / 'frame-map.json')
            with self.assertRaisesRegex(module.SourceError, 'not synchronized'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
            rows[1]['camera_frame_ids']['approach'] = 2
            (base / 'frame-map.json').write_text(json.dumps(rows))
            p['frame_map_ref'] = hashed(base / 'frame-map.json')
            del p['camera_media_refs']['approach']
            with self.assertRaisesRegex(module.SourceError, 'four original camera'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)

    def test_rejects_media_change_frame_loss_and_profile_drift(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            (base / 'overview.mkv').write_bytes(b'corrupted')
            with self.assertRaisesRegex(module.SourceError, 'source hash mismatch'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi',
                            '-i', 'color=c=blue:s=16x16:r=20', '-frames:v', '2',
                            '-c:v', 'ffv1', str(base / 'overview.mkv')], check=True)
            p['camera_media_refs']['overview'] = hashed(base / 'overview.mkv')
            with self.assertRaisesRegex(module.SourceError, 'frame count differs'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as d:
            p = build(Path(d))
            profile = {v: (16, 16) for v in module.VIEWS}
            profile['overview'] = (32, 16)
            with self.assertRaisesRegex(module.SourceError, 'profile source differs'):
                module.audit_saved_delivery(p, d, profile=profile, diagnostic_fixture=True)

    def test_rejects_unbound_camera_profile(self):
        with tempfile.TemporaryDirectory() as d:
            p = build(Path(d))
            p['camera_profile_sha256'] = 'stale'
            with self.assertRaisesRegex(module.SourceError, 'profile hash binding differs'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)

    def test_rejects_unmarked_diagnostic_profile(self):
        with tempfile.TemporaryDirectory() as d:
            p = build(Path(d))
            with self.assertRaisesRegex(module.SourceError, 'diagnostic fixture flag'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS})

    def test_rejects_unbound_lawful_context_and_other_device_source(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            (base / 'reviewed-pedestrian-context.json').write_text('{}')
            with self.assertRaisesRegex(module.SourceError, 'source hash mismatch'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            context = json.loads((base / 'context.json').read_text())
            context['participant_context_refs'] = {}
            (base / 'context.json').write_text(json.dumps(context))
            p['context_ref'] = hashed(base / 'context.json')
            with self.assertRaisesRegex(module.SourceError, 'participant context identity differs'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            p = build(base)
            (base / 'other-devices.json').write_text('{}')
            with self.assertRaisesRegex(module.SourceError, 'source hash mismatch'):
                module.audit_saved_delivery(p, d, profile={v: (16, 16) for v in module.VIEWS}, diagnostic_fixture=True)
