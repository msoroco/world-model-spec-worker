import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_saved_audit import rows, PREFIX


MODULE = Path(__file__).resolve().parents[1] / 'delivery_audit.py'
spec = importlib.util.spec_from_file_location('trail_delivery_audit', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(root, case='all_prerequisites'):
    case_id = PREFIX + case
    history = root / 'native.jsonl'
    raw = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows(case)).encode()
    history.write_bytes(raw)
    cameras = {}
    for camera in audit.CAMERAS:
        body = ('diagnostic-' + camera).encode()
        (root / (camera + '.mp4')).write_bytes(body)
        cameras[camera] = {'path': camera + '.mp4', 'sha256': sha(body)}
    acquisition = {
        'case_id': case_id, 'cell_id': 'C143687', 'frame_count': 900,
        'fps': 20, 'history': {'path': history.name, 'sha256': sha(raw)},
        'camera_media': cameras,
    }
    path = root / 'acquisition.json'
    path.write_text(json.dumps(acquisition), encoding='utf-8')
    return path, acquisition


class DeliveryAuditTests(unittest.TestCase):
    def test_full_video_decode_joins_sealed_trail_source(self):
        scratch = MODULE.parents[2] / '.runtime-work' / 'c143687-decoded-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root = Path(tmp)
            path, data = fixture(root)
            for camera in audit.CAMERAS:
                video = root / (camera + '.mp4')
                completed = subprocess.run([
                    'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:s=16x16:r=20:d=45', '-frames:v', '900',
                    '-c:v', 'mpeg4', '-y', str(video)], capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                data['camera_media'][camera]['sha256'] = sha(video.read_bytes())
            path.write_text(json.dumps(data), encoding='utf-8')
            report = audit.audit_decoded(root, path, data['case_id'],
                                         expected_dimensions={name: (16, 16) for name in audit.CAMERAS})
            self.assertTrue(report['full_video_decode'])
            self.assertEqual(report['decoded_view_frames'], 3600)
            self.assertFalse(report['physical_completion'])
            with (root / 'front.mp4').open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit.audit_decoded(root, path, data['case_id'])
            completed = subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=black:s=16x16:r=10:d=90', '-frames:v', '900',
                '-c:v', 'mpeg4', '-y', str(root / 'front.mp4')],
                capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            data['camera_media']['front']['sha256'] = sha((root / 'front.mp4').read_bytes())
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'rate differs'):
                audit.audit_decoded(root, path, data['case_id'])

    def test_source_inventory_withholds_physical_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, _ = fixture(root)
            result = audit.audit_saved(root, path, PREFIX + 'all_prerequisites')
            self.assertTrue(result['native_source'])
            self.assertEqual(set(result['camera_media']), set(audit.CAMERAS))
            self.assertFalse(result['full_video_decode'])
            self.assertFalse(result['physical_completion'])

    def test_reject_missing_and_tampered_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, data = fixture(root)
            (root / 'front.mp4').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'front camera hash mismatch'):
                audit.audit_saved(root, path, data['case_id'])
            (root / 'front.mp4').unlink()
            with self.assertRaisesRegex(ValueError, 'saved source missing'):
                audit.audit_saved(root, path, data['case_id'])

    def test_reject_case_duration_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, data = fixture(root)
            with self.assertRaisesRegex(ValueError, 'acquisition case'):
                audit.audit_saved(root, path, PREFIX + 'not_designated')
            data['frame_count'] = 899
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'frame contract'):
                audit.audit_saved(root, path, data['case_id'])
            data['frame_count'] = 900
            data['history']['path'] = '../native.jsonl'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'outside attempt'):
                audit.audit_saved(root, path, data['case_id'])
