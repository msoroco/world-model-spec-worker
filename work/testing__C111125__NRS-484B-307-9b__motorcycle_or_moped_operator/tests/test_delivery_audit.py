import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('delivery_audit', Path(__file__).resolve().parents[1] / 'delivery_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        def ref(name, data):
            p = self.root / name
            p.write_text(json.dumps(data))
            return {'path': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        self.ref = ref
        self.rows = [{'frame': i, 'official_head_id': 'head-17', 'actor_id': 'ego-1'} for i in range(900)]
        names = ('overview', 'approach', 'reference_corner', 'driver_reference')
        self.manifest = {
            'case_id': 'case-1', 'assignment_id': 'assignment-1',
            'law_id': 'NRS-484B-307-9b', 'actor': 'motorcycle_or_moped_operator',
            'fps': 20, 'duration_frames': 900, 'official_head_id': 'head-17', 'actor_id': 'ego-1',
            'sources': {key: ref(key + '.json', self.rows if key == 'original_events' else {'kind': key})
                        for key in ('original_events', 'map', 'route', 'signal', 'stop_reference', 'crosswalk', 'cause')},
            'camera_views': {name: {'source': ref(name + '.json', {'view': name}),
                                     'decoded_frames': 900, 'fps': 20,
                                     'width': 1280, 'height': 720,
                                     'first_original_frame': 0, 'last_original_frame': 899}
                             for name in names},
            'pixel_review_status': 'pending',
        }

    def test_complete_saved_inventory(self):
        out = audit.audit_saved(self.root, self.manifest)
        self.assertEqual(out['original_frames'], 900)
        self.assertFalse(out['physical_acceptance'])

    def test_missing_camera_and_misalignment_rejected(self):
        self.manifest['camera_views'].pop('driver_reference')
        with self.assertRaisesRegex(audit.DeliveryError, 'four-view'):
            audit.audit_saved(self.root, self.manifest)
        self.manifest['camera_views']['driver_reference'] = {
            'source': self.ref('new.json', {}), 'decoded_frames': 900, 'fps': 20,
            'width': 1280, 'height': 720, 'first_original_frame': 1, 'last_original_frame': 899}
        with self.assertRaisesRegex(audit.DeliveryError, 'alignment'):
            audit.audit_saved(self.root, self.manifest)

    def test_reused_camera_source_rejected(self):
        self.manifest['camera_views']['approach']['source'] = self.manifest['camera_views']['overview']['source']
        with self.assertRaisesRegex(audit.DeliveryError, 'distinct'):
            audit.audit_saved(self.root, self.manifest)

    def test_rejects_hash_and_frame_loss(self):
        self.manifest['sources']['map']['sha256'] = '0'*64
        with self.assertRaisesRegex(audit.DeliveryError, 'hash mismatch'):
            audit.audit_saved(self.root, self.manifest)
        self.manifest['sources']['map'] = self.ref('map.json', {'kind': 'map'})
        self.manifest['sources']['original_events'] = self.ref('original_events.json', self.rows[:-1])
        with self.assertRaisesRegex(audit.DeliveryError, 'frame count'):
            audit.audit_saved(self.root, self.manifest)

    def test_negative_causal_case_preserves_absence_of_source(self):
        self.manifest['case_id'] = 'assignment__no_causal_record'
        self.manifest['sources'].pop('cause')
        self.manifest['cause_status'] = 'not_established'
        self.assertEqual(audit.audit_saved(self.root, self.manifest)['original_frames'], 900)
        self.manifest['cause_status'] = 'failed_detection'
        with self.assertRaisesRegex(audit.DeliveryError, 'negative causal case'):
            audit.audit_saved(self.root, self.manifest)


if __name__ == '__main__': unittest.main()
