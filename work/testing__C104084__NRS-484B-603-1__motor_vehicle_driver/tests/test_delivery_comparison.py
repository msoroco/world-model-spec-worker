import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
from delivery_comparison import compare
from saved_crest_audit import ASSIGNMENT
from saved_crest_bundle import assemble
from test_saved_crest_media import media_fixture


def bundle(root, profile, capture_ref, *, other_offset=0):
    source = root / 'original'
    source.mkdir(parents=True)
    fixture = media_fixture(source)
    map_path = source / 'native-map.xodr'
    map_path.write_text('one original loaded crest map\n', encoding='utf-8')
    if profile == 'late_decrease' or other_offset:
        motion_path = source / fixture['motion_source']['path']
        frames = json.loads(motion_path.read_text())
        for i, row in enumerate(frames):
            if profile == 'late_decrease':
                row['ego_speed_mps'] = 10 if i < 400 else 8
            row['other_s_m'] += other_offset
        motion_path.write_text(json.dumps(frames) + '\n')
    sources = {'native_map_source': str(map_path)}
    for key in ('grade_source', 'motion_source', 'context_source',
                'other_route_source', 'frame_map_source', 'prescribed_limit_source'):
        sources[key] = str(source / fixture[key]['path'])
    spec = {'profile': profile, 'acquisition_kind': 'original_native',
            'native_map_sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
            'native_capture_ref': capture_ref,
            'approach_start_m': fixture['approach_start_m'],
            'camera_dimensions': fixture['camera_dimensions'],
            'sources': sources,
            'cameras': {name: str(source / binding['path'])
                        for name, binding in fixture['camera_sources'].items()}}
    destination = root / 'sealed'
    assemble(spec, destination, expected_case=ASSIGNMENT + '__' + profile)
    return destination


class DeliveryComparisonTests(unittest.TestCase):
    def test_source_bound_audits_and_distinct_measured_profiles(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            left = bundle(root / 'left', 'early_decrease', 'native-left')
            right = bundle(root / 'right', 'late_decrease', 'native-right')
            proof = compare(left, right, 'early_vs_late_precrest_decrease')
            self.assertEqual(proof['case_ids'], [ASSIGNMENT + '__early_decrease',
                                                  ASSIGNMENT + '__late_decrease'])
            self.assertFalse(proof['physical_acceptance'])
            self.assertNotEqual(proof['measured_profiles'][0]['first_speed_decrease_station_m'],
                                proof['measured_profiles'][1]['first_speed_decrease_station_m'])
            manifest_path = right / 'manifest.json'
            original_manifest = manifest_path.read_bytes()
            manifest = json.loads(manifest_path.read_text())
            manifest['native_capture_ref'] = 'native-left'
            manifest_path.write_text(json.dumps(manifest) + '\n')
            with self.assertRaisesRegex(ValueError, 'manifest seal'):
                compare(left, right, 'early_vs_late_precrest_decrease')
            manifest_path.write_bytes(original_manifest)
            # A changed encoded original is rejected before comparison.
            (right / 'front.mkv').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash'):
                compare(left, right, 'early_vs_late_precrest_decrease')

    def test_rejects_reused_capture_and_changed_other_motion(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            left = bundle(root / 'left', 'early_decrease', 'native-left')
            reused = bundle(root / 'reused', 'late_decrease', 'native-left')
            with self.assertRaisesRegex(ValueError, 'distinct original Native'):
                compare(left, reused, 'early_vs_late_precrest_decrease')
            changed = bundle(root / 'changed', 'late_decrease', 'native-right',
                             other_offset=-2)
            with self.assertRaisesRegex(ValueError, 'opposing-vehicle motion differs'):
                compare(left, changed, 'early_vs_late_precrest_decrease')


if __name__ == '__main__':
    unittest.main()
