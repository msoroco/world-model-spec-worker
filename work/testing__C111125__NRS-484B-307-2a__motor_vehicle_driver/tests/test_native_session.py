import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import native_session
from delivery_audit import VIEWS
from test_native_capture import Ego, World, green
from test_native_scene import ref, site


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        scratch_root = REPO / '.runtime-work/c111125-2a-session-tests'
        scratch_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch_root)
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / 'attempt'
        self.root.mkdir()
        self.scratch = base / 'camera-scratch'
        self.scratch.mkdir()
        self.site = site(self.root)
        self.site_ref = ref(self.root, 'site.json', self.site)
        self.profile = {view: (16, 16) for view in VIEWS}
        self.profile_ref = ref(self.root, 'profile.json',
                               {'fps': 20, 'views': {view: [16, 16] for view in VIEWS}})
        other_devices = ref(self.root, 'other-devices.json', {'inventory': []})
        self.context_ref = ref(self.root, 'context.json',
                               {'official_head_id': self.site['official_head_id'],
                                'ego_approach_id': self.site['ego_approach_id'],
                                'other_devices_ref': other_devices,
                                'participant_context_refs': {}})

    def _run(self, audit_result=None):
        world = World()
        ego = Ego(world)
        with patch.object(native_session, 'OriginalCameraRecorder') as factory, \
                patch.object(native_session, 'audit_saved_delivery') as audit:
            recorder = factory.return_value
            recorder.read.side_effect = lambda snapshot: {view: snapshot.frame for view in VIEWS}
            recorder.finish.return_value = {view: {'path': view + '.mkv', 'sha256': 'a' * 64}
                                            for view in VIEWS}
            if isinstance(audit_result, Exception):
                audit.side_effect = audit_result
            else:
                audit.return_value = {'software_audit_passed': True}
            if isinstance(audit_result, Exception):
                with self.assertRaisesRegex(ValueError, str(audit_result)):
                    native_session.capture_with_media(
                        world, ego, None, self.site, self.site_ref, 'green_clear',
                        green, self.root, {view: object() for view in VIEWS},
                        self.scratch, self.profile_ref, self.context_ref,
                        profile=self.profile, diagnostic_fixture=True)
                result = None
            else:
                result = native_session.capture_with_media(
                    world, ego, None, self.site, self.site_ref, 'green_clear',
                    green, self.root, {view: object() for view in VIEWS},
                    self.scratch, self.profile_ref, self.context_ref,
                    profile=self.profile, diagnostic_fixture=True)
            recorder.close.assert_called_once()
            audit.assert_called_once()
            return result, ego

    def test_events_frame_map_media_audit_and_final_receipt_join(self):
        result, ego = self._run()
        self.assertTrue(ego.braked)
        self.assertEqual(result['measurement']['frame_count'], 900)
        self.assertEqual(result['packet']['camera_profile_sha256'], self.profile_ref['sha256'])
        self.assertEqual(result['packet']['frame_map_ref']['path'], 'original-frame-map.json')
        receipt = json.loads((self.root / 'media-capture-receipt.json').read_text())
        self.assertTrue(receipt['camera_capture_complete'])
        self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_failed_media_audit_never_publishes_complete_receipt(self):
        result, ego = self._run(ValueError('media source mismatch'))
        self.assertIsNone(result)
        self.assertTrue(ego.braked)
        self.assertFalse((self.root / 'media-capture-receipt.json').exists())
        partial = json.loads((self.root / 'original-capture-receipt.json').read_text())
        self.assertFalse(partial['camera_capture_complete'])

    def test_changed_camera_profile_rejected_before_listeners(self):
        (self.root / 'profile.json').write_text('{}\n')
        with patch.object(native_session, 'OriginalCameraRecorder') as factory:
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                native_session.capture_with_media(
                    World(), Ego(World()), None, self.site, self.site_ref,
                    'green_clear', green, self.root, {}, self.scratch,
                    self.profile_ref, self.context_ref,
                    profile=self.profile, diagnostic_fixture=True)
            factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
