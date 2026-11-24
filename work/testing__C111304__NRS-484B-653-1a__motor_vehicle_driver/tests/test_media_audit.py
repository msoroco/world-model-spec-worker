import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('media_audit', ROOT / 'media_audit.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(attempt):
    case_id = module.CASE_PREFIX + 'person_north_early'
    plan = {'cameras': {name: {'width': 64, 'height': 64} for name in module.CAMERAS}}
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    receipt = {'case_id': case_id, 'frame_count': 900, 'original_fps': 20,
               'camera_plan_sha256': plan_hash}
    (attempt / 'native-receipt.json').write_text(json.dumps(receipt) + '\n')
    cameras = {}
    for name, color in zip(module.CAMERAS, ('red', 'green', 'blue', 'yellow')):
        path = attempt / (name + '.mkv')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        f'color=c={color}:s=64x64:r=20:d=45', '-frames:v', '900',
                        '-c:v', 'ffv1', str(path)], check=True, capture_output=True)
        cameras[name] = {'path': path.name, 'sha256': sha(path)}
    inventory = {'case_id': case_id, 'source_kind': 'synthetic_fixture',
                 'native_receipt_sha256': sha(attempt / 'native-receipt.json'),
                 'cameras': cameras}
    return receipt, inventory, plan


class MediaAuditTests(unittest.TestCase):
    def test_full_four_camera_decode(self):
        with TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            receipt, inventory, plan = fixture(attempt)
            with self.assertRaisesRegex(ValueError, 'original encoded camera source required'):
                module.audit_media(attempt, receipt, inventory, plan)
            result = module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)
            self.assertEqual(set(result['cameras']), set(module.CAMERAS))
            self.assertTrue(all(x['full_decode'] and x['frames'] == 900
                                for x in result['cameras'].values()))
            self.assertFalse(result['actual_body_visibility'])

    def test_rejects_missing_or_tampered_media_and_plan(self):
        with TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            receipt, inventory, plan = fixture(attempt)
            inventory['cameras']['front']['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)
            inventory['cameras']['front']['sha256'] = sha(attempt / 'front.mkv')
            plan['cameras']['front']['width'] = 128
            with self.assertRaisesRegex(ValueError, 'camera plan source hash mismatch'):
                module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)
            plan['cameras']['front']['width'] = 64
            inventory['cameras'].pop('right')
            with self.assertRaisesRegex(ValueError, 'four camera entries required'):
                module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)

    def test_rejects_truncated_and_redirected_media(self):
        with TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            receipt, inventory, plan = fixture(attempt)
            (attempt / 'front.mkv').write_bytes((attempt / 'front.mkv').read_bytes()[:128])
            inventory['cameras']['front']['sha256'] = sha(attempt / 'front.mkv')
            with self.assertRaises(ValueError):
                module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)
            inventory['cameras']['front']['path'] = '../outside.mkv'
            with self.assertRaisesRegex(ValueError, 'missing, redirected or reused'):
                module.audit_media(attempt, receipt, inventory, plan, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
