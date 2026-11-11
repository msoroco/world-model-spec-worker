import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit_attempt


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self, root, official=False):
        short = 'official-device' if official else 'ending-yields'
        source = json.loads((ROOT / ('diagnostic-' + short + '.json')).read_text())['files']
        for name in ('intersection_topology.json', 'intersection_participants.jsonl',
                     'video_frames.jsonl', 'trace.jsonl',
                     'official_device_context.json', 'official_device_states.jsonl',
                     'control_inventory.json'):
            if name in source:
                (root / name).write_text(source[name])
        construction = json.loads((ROOT / ('construction-' + short + '.json')).read_text())
        config = next(f['content'] for f in construction['files'] if f['path'] == 'config.json')
        (root / 'config.json').write_text(config)
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (root / (name + '.mkv')).write_bytes(b'synthetic camera test')
        from delivery_audit import digest
        from ending_road_measurement import measure
        base_names = ('intersection_topology.json', 'intersection_participants.jsonl',
                      'video_frames.jsonl', 'trace.jsonl') + (() if official else ('control_inventory.json',))
        measurements = {'intersection_observation': {
            'value': measure(root / 'intersection_topology.json',
                             root / 'intersection_participants.jsonl'),
            'sources': {name: digest(root / name) for name in base_names}}}
        if official:
            from ending_road_official_finalizer import measure_official_device
            device_names = ('official_device_context.json', 'official_device_states.jsonl',
                            'intersection_topology.json', 'video_frames.jsonl')
            measurements['official_device_observation'] = {
                'value': measure_official_device(root / 'official_device_context.json',
                         root / 'official_device_states.jsonl',
                         root / 'intersection_topology.json', root / 'video_frames.jsonl'),
                'sources': {name: digest(root / name) for name in device_names}}
        return {'case_id': json.loads(config)['selected_case_id'], 'measurements': measurements}


    def test_original_source_and_four_camera_audit(self):
        for official in (False, True):
            with self.subTest(official=official), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                report = self.fixture(root, official)
                frames = len((root / 'video_frames.jsonl').read_text().splitlines())
                def fake_decode(path, count, *, mapping_sha256):
                    self.assertEqual(count, frames)
                    self.assertEqual(len(mapping_sha256), 64)
                    return {'frames': count}
                audited = audit_attempt(root, report, decoder=fake_decode)
                self.assertEqual(audited['frame_count'], frames)
                self.assertEqual(len(audited['camera_decodes']), 4)
                self.assertFalse(audited['physical_visibility_claimed'])
                (root / 'overview.mkv').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing named'):
                    audit_attempt(root, report, decoder=fake_decode)
                (root / 'intersection_topology.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'hash differs'):
                    audit_attempt(root, report, decoder=fake_decode)


if __name__ == '__main__':
    unittest.main()
