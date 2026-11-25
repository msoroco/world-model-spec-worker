import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import native_capture
from saved_crossing import ASSIGNMENT, CAMERAS, process_saved
from delivery_audit import audit_delivery
from comparison_audit import audit_attempt_pair


class World:
    def __init__(self):
        self.frame = 0

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        stamp = type('Stamp', (), {'elapsed_seconds': self.frame / 20})()
        return type('Snapshot', (), {'frame': self.frame, 'timestamp': stamp})()


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111329-native-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / 'attempt'
        self.attempt.mkdir()
        sources = {}
        for name in ('map', 'corner_survey', 'authorization', 'device_inventory',
                     'exception_review'):
            path = self.root / (name + '.txt')
            path.write_text('reviewed ' + name + '\n')
            sources[name] = {'path': str(path),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.site = {'sources': sources, 'coordinate_frame': 'map_xy_m',
                     'corners_clockwise': [[0, 0], [10, 0], [10, 10], [0, 10]],
                     'pedestrian_route': [[0, 0], [5, 5], [10, 10]],
                     'governing_device': {'id': 'ped-1', 'authority_record_id': 'order-1',
                                          'instruction_record_id': 'order-1-diagonal',
                                          'placement_record_id': 'survey-1',
                                          'governs': 'pedestrian_diagonal',
                                          'diagonal_authorized': True},
                     'observed_device_ids': ['ped-1'],
                     'exception_484b_290_review': 'unresolved'}
        self.case = ASSIGNMENT + '__instruction_changes_during_crossing'

    def readers(self, *, stale=False):
        def walker(snapshot):
            coordinate = 10 * (snapshot.frame - 1) / 899
            return {'source_kind': 'native_walker_readback',
                    'original_frame': snapshot.frame, 'walker_id': 7,
                    'center_xy': [coordinate, coordinate]}
        def device(snapshot, identity):
            return {'source_kind': 'native_device_readback',
                    'original_frame': snapshot.frame - int(stale),
                    'device_id': identity,
                    'source_sha256': self.site['sources']['device_inventory']['sha256'],
                    'pedestrian_governance': 'diagonal',
                    'instruction': 'diagonal_walk' if snapshot.frame < 500
                                   else 'diagonal_dont_walk'}
        def cameras(snapshot):
            return {name: snapshot.frame for name in CAMERAS}
        return walker, device, cameras

    def test_900_original_frames_and_local_source_copy(self):
        walker, device, cameras = self.readers()
        result = native_capture.capture(World(), self.site, self.case, self.attempt,
                                        walker, device, cameras,
                                        [[2, 2], [8, 2], [8, 8], [2, 8]],
                                        diagnostic=True)
        self.assertEqual(result['measurement']['original_frames'], 900)
        self.assertFalse(result['measurement']['full_video_decode'])
        self.assertEqual(result['acquisition']['camera_media_status'],
                         'not_acquired_by_frame_reader')
        local = json.loads((self.attempt / 'site.json').read_text())
        for item in local['sources'].values():
            self.assertEqual((self.attempt / item['path']).parent, self.attempt)

    def test_stale_governing_device_rejected_before_acquisition(self):
        walker, device, cameras = self.readers(stale=True)
        with self.assertRaisesRegex(ValueError, 'walker/device original frame differs'):
            native_capture.capture(World(), self.site, self.case, self.attempt,
                                   walker, device, cameras,
                                   [[2, 2], [8, 2], [8, 8], [2, 8]],
                                   diagnostic=True)
        self.assertFalse((self.attempt / 'acquisition.json').exists())

    def test_original_camera_pixels_are_encoded_and_fully_decoded(self):
        walker, device, cameras = self.readers()
        profile = {name: (2, 2) for name in CAMERAS}
        def images(snapshot):
            return {name: SimpleNamespace(frame=snapshot.frame, width=2, height=2,
                                          raw_data=bytes((snapshot.frame % 251, 25, 40, 255)) * 4)
                    for name in CAMERAS}
        result = native_capture.capture(World(), self.site, self.case, self.attempt,
                                        walker, device, cameras,
                                        [[2, 2], [8, 2], [8, 8], [2, 8]],
                                        diagnostic=True, camera_image_reader=images,
                                        diagnostic_camera_profile=profile)
        self.assertEqual(result['acquisition']['camera_media_status'], 'full_original_decode')
        audit = json.loads((self.attempt / 'camera-media-audit.json').read_text())
        self.assertTrue(all(row['frames'] == 900 for row in audit['cameras'].values()))
        self.assertEqual(audit['physical_visibility'], 'unverified')
        self.assertTrue(result['measurement']['full_video_decode'])
        diagnostic = audit_delivery(self.attempt, self.case, allow_diagnostic=True)
        self.assertTrue(diagnostic['software_checks_passed'])
        self.assertFalse(diagnostic['physical_completion'])
        with self.assertRaisesRegex(ValueError, 'diagnostic attempt'):
            audit_delivery(self.attempt, self.case)
        (self.attempt / 'camera-media-audit.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'receipt hash mismatch'):
            process_saved(self.attempt, self.case, self.attempt / 'second-measurement.json',
                          allow_diagnostic=True)

    def test_non_diagnostic_capture_requires_adapter_attestation(self):
        walker, device, cameras = self.readers()
        with self.assertRaisesRegex(ValueError, 'attestation required'):
            native_capture.capture(World(), self.site, self.case, self.attempt,
                                   walker, device, cameras,
                                   [[2, 2], [8, 2], [8, 8], [2, 8]],
                                   diagnostic=False)
        self.assertEqual(list(self.attempt.iterdir()), [])

    def test_exact_saved_comparison_replays_two_original_attempts(self):
        walker, device, cameras = self.readers()
        reference_case = ASSIGNMENT + '__permissive_whole_crossing'
        variant_case = ASSIGNMENT + '__prohibitive_whole_crossing'
        def instruction_reader(instruction):
            def read(snapshot, identity):
                return {**device(snapshot, identity), 'instruction': instruction}
            return read
        native_capture.capture(World(), self.site, reference_case, self.attempt,
                               walker, instruction_reader('diagonal_walk'), cameras,
                               [[2, 2], [8, 2], [8, 8], [2, 8]], diagnostic=True)
        variant = self.root / 'variant'
        variant.mkdir()
        native_capture.capture(World(), self.site, variant_case, variant,
                               walker, instruction_reader('diagonal_dont_walk'), cameras,
                               [[2, 2], [8, 2], [8, 8], [2, 8]], diagnostic=True)
        receipt = audit_attempt_pair('diagonal_instruction_permissive_vs_prohibitive',
                                     self.attempt, variant, allow_diagnostic=True)
        self.assertTrue(receipt['comparison_verified'])
        self.assertEqual(receipt['physical_realization'], 'unconfirmed')
        with self.assertRaisesRegex(ValueError, 'diagnostic'):
            audit_attempt_pair('diagonal_instruction_permissive_vs_prohibitive',
                               self.attempt, variant)

    def test_three_original_media_attempts_both_comparisons_and_missing_source(self):
        walker, device, cameras = self.readers()
        profile = {name: (2, 2) for name in CAMERAS}
        def images(snapshot):
            return {name: SimpleNamespace(frame=snapshot.frame, width=2, height=2,
                                          raw_data=bytes((snapshot.frame % 251, 25, 40, 255)) * 4)
                    for name in CAMERAS}
        attempts = {}
        for suffix in ('permissive_whole_crossing', 'prohibitive_whole_crossing',
                       'instruction_changes_during_crossing'):
            case = ASSIGNMENT + '__' + suffix
            root = self.root / suffix
            root.mkdir()
            def read_instruction(snapshot, identity, selected=suffix):
                instruction = ('diagonal_dont_walk' if selected == 'prohibitive_whole_crossing'
                               or (selected == 'instruction_changes_during_crossing'
                                   and snapshot.frame >= 500) else 'diagonal_walk')
                return {**device(snapshot, identity), 'instruction': instruction}
            native_capture.capture(World(), self.site, case, root, walker,
                                   read_instruction, cameras,
                                   [[2, 2], [8, 2], [8, 8], [2, 8]], diagnostic=True,
                                   camera_image_reader=images,
                                   diagnostic_camera_profile=profile)
            saved = process_saved(root, case, root / 'saved-only.json',
                                  allow_diagnostic=True)
            self.assertTrue(saved['full_video_decode'])
            self.assertTrue(audit_delivery(root, case,
                                           allow_diagnostic=True)['software_checks_passed'])
            attempts[suffix] = root
        for comparison, variant in (
            ('diagonal_instruction_permissive_vs_prohibitive', 'prohibitive_whole_crossing'),
            ('diagonal_instruction_phase_change', 'instruction_changes_during_crossing'),
        ):
            receipt = audit_attempt_pair(comparison,
                                         attempts['permissive_whole_crossing'],
                                         attempts[variant], allow_diagnostic=True)
            self.assertTrue(receipt['comparison_verified'])
            self.assertEqual(receipt['physical_realization'], 'unconfirmed')
        missing = attempts['instruction_changes_during_crossing']
        (missing / 'overview.mkv').unlink()
        with self.assertRaisesRegex(ValueError, 'missing|escapes'):
            process_saved(missing, ASSIGNMENT + '__instruction_changes_during_crossing',
                          missing / 'missing-source-result.json', allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
