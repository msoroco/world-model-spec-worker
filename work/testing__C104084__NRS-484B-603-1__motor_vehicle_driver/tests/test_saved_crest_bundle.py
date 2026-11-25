import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
from saved_crest_audit import ASSIGNMENT
from saved_crest_bundle import assemble, verify_bundle
from saved_delivery_audit import audit as audit_delivery
from test_saved_crest_media import media_fixture


class SavedCrestBundleTests(unittest.TestCase):
    def test_seals_complete_observed_sources_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            root = Path(tmp)
            original = root / 'source'
            original.mkdir()
            fixture = media_fixture(original)
            native_map = original / 'native-map.xodr'
            native_map.write_text('loaded Native OpenDRIVE source\n', encoding='utf-8')
            spec = {'profile': 'early_decrease', 'acquisition_kind': 'original_native',
                    'native_map_sha256': hashlib.sha256(native_map.read_bytes()).hexdigest(),
                    'native_capture_ref': 'native-run-001',
                    'approach_start_m': fixture['approach_start_m'],
                    'camera_dimensions': fixture['camera_dimensions'],
                    'sources': {'native_map_source': str(native_map),
                                **{key: str(original / fixture[key]['path'])
                                for key in ('grade_source', 'motion_source',
                                            'context_source', 'other_route_source',
                                            'frame_map_source', 'prescribed_limit_source')}},
                    'cameras': {key: str(original / binding['path'])
                                for key, binding in fixture['camera_sources'].items()}}
            case = ASSIGNMENT + '__early_decrease'
            dest = root / 'sealed'
            proof = assemble(spec, dest, expected_case=case)
            self.assertEqual(proof['frame_count'], 900)
            self.assertEqual(proof['native_capture_ref'], 'native-run-001')
            self.assertEqual(set(proof['camera_decodes']), {'front', 'left', 'right', 'rear'})
            sealed = json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(sealed['native_map_sha256'], spec['native_map_sha256'])
            self.assertEqual(sealed['native_map_source']['sha256'], spec['native_map_sha256'])
            self.assertFalse(proof['checks']['physical_completion'])
            self.assertEqual(verify_bundle(dest, sealed, expected_case=case)['frame_count'], 900)
            delivery = audit_delivery(dest, expected_case=case)
            self.assertEqual(delivery['frame_count'], 900)
            self.assertEqual(delivery['decoded_camera_count'], 4)
            self.assertFalse(delivery['physical_acceptance'])
            finalized_path = dest / 'finalized.json'
            original_finalized = finalized_path.read_bytes()
            altered = json.loads(original_finalized)
            altered['checks']['physical_completion'] = True
            finalized_path.write_text(json.dumps(altered) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'finalizer differs'):
                audit_delivery(dest, expected_case=case)
            finalized_path.write_bytes(original_finalized)
            (dest / 'unplanned.txt').write_text('extra\n')
            with self.assertRaisesRegex(ValueError, 'inventory differs'):
                audit_delivery(dest, expected_case=case)
            (dest / 'unplanned.txt').unlink()
            with self.assertRaises(FileExistsError):
                assemble(spec, dest, expected_case=case)
            (dest / 'front.mkv').write_bytes(b'changed')
            from saved_crest_finalizer import finalize
            with self.assertRaisesRegex(ValueError, 'hash'):
                finalize(dest, sealed, expected_case=case)
            (dest / 'native-map.xodr').write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                verify_bundle(dest, sealed, expected_case=case)
            spec['native_map_sha256'] = 'a' * 64
            with self.assertRaisesRegex(ValueError, 'map bytes differ'):
                assemble(spec, root / 'wrong-map', expected_case=case)
            self.assertFalse((root / 'wrong-map').exists())
            self.assertFalse(any(root.glob('crest-bundle-*')))
            spec['native_map_sha256'] = hashlib.sha256(native_map.read_bytes()).hexdigest()
            Path(spec['cameras']['front']).write_bytes(b'bad camera')
            with self.assertRaises(ValueError):
                assemble(spec, root / 'bad-camera', expected_case=case)
            self.assertFalse((root / 'bad-camera').exists())
            self.assertFalse(any(root.glob('crest-bundle-*')))

    def test_rejects_missing_camera_and_unbound_native_origin(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            spec = {'profile': 'steady_approach', 'acquisition_kind': 'original_native',
                    'native_map_sha256': 'bad', 'native_capture_ref': 'run',
                    'sources': {}, 'cameras': {}}
            case = ASSIGNMENT + '__steady_approach'
            with self.assertRaisesRegex(ValueError, 'map hash'):
                assemble(spec, Path(tmp) / 'sealed', expected_case=case)
            self.assertFalse((Path(tmp) / 'sealed').exists())


if __name__ == '__main__':
    unittest.main()
