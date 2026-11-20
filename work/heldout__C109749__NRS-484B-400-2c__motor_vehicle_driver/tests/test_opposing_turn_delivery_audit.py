import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import opposing_turn_delivery_audit as delivery
from opposing_turn_measurement import measure


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = delivery.PREFIX + 'rear_pass_no_device'
        (self.root / 'config.json').write_text(json.dumps({'selected_case_id': self.case}))
        (self.root / 'fixture-provenance.json').write_text('{"kind":"synthetic_diagnostic"}\n')
        (self.root / 'topology_original.json').write_text(json.dumps({
            'both_highways_two_directional': True, 'same_intersection': True,
            'opposing_approaches': True}))
        (self.root / 'devices_original.json').write_text('{"governing_device":"none"}\n')
        a, b, mapping, trace = [], [], [], []
        for index in range(3):
            def row(x, y, identity, heading):
                return {'frame': index, 'time_s': index*.05, 'center_xy': [x, y],
                        'heading_xy': heading, 'native_actor_id': identity,
                        'ground_corners_xy': [[x-.2,y-.2],[x+.2,y-.2],
                                              [x+.2,y+.2],[x-.2,y+.2]],
                        'in_intersection': True, 'turning_left': True}
            a.append(row(index, 0, 1, [1, 0]))
            b.append(row(3-index, 1, 2, [-1, 0]))
            mapping.append({'video_frame': index, 'carla_frame': index, 'time_s': index*.05})
            trace.append({'frame': index, 'time_s': index*.05})
        for name, value in zip(('subject_original.jsonl','opposing_original.jsonl',
                                'video_frames.jsonl','trace.jsonl'),(a,b,mapping,trace)):
            (self.root / name).write_text(''.join(json.dumps(row)+'\n' for row in value))
        observed = measure(*(self.root / name for name in delivery.SOURCES[:4]))
        sources = {name: delivery.digest(self.root / name) for name in delivery.SOURCES}
        (self.root / 'analysis-report.json').write_text(json.dumps({
            'case_id': self.case, 'measurements': {'opposing_turn_geometry': {
                'value': observed, 'sources': sources}}}))
        (self.root / 'result.json').write_text(json.dumps({
            'case_id': self.case, 'measured_values': {'opposing_turn_geometry': observed}}))
        for name in delivery.CAMERAS:
            (self.root / (name+'.mkv')).write_bytes(b'synthetic video placeholder')
        (self.root / 'raw.mkv').write_bytes(b'synthetic composed placeholder')

    def _fake_decode(self, path, frames, *, mapping_sha256, receipt):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        self.assertEqual(frames, 3)
        self.assertEqual(mapping_sha256, delivery.digest(self.root / 'video_frames.jsonl'))
        Path(receipt).write_text('{"fixture_decode":true}\n')
        return {'auditor_sha256': 'fixture-media-auditor',
                'video_sha256': delivery.digest(path)}

    def test_original_join_and_named_camera_protocol(self):
        with patch.object(delivery.media, 'audit', self._fake_decode):
            result = delivery.audit(self.case, self.root, diagnostic_fixture=True)
        self.assertEqual(result['participant_ids'], [1, 2])
        self.assertEqual(result['frames'], 3)
        self.assertTrue(result['checks']['all_participants'])
        self.assertFalse(result['checks']['actual_pixels'])

    def test_stale_actor_and_missing_camera_rejected(self):
        path = self.root / 'opposing_original.jsonl'
        original = path.read_text()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['center_xy'][0] += 1
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'measurement differs'):
            delivery.audit(self.case, self.root, diagnostic_fixture=True)
        path.write_text(original)
        (self.root / 'overview.mkv').unlink()
        with patch.object(delivery.media, 'audit', self._fake_decode):
            with self.assertRaises(FileNotFoundError):
                delivery.audit(self.case, self.root, diagnostic_fixture=True)

    def test_native_mode_rejects_fixture_without_closure(self):
        with patch.object(delivery.media, 'audit', self._fake_decode):
            with self.assertRaisesRegex(ValueError, 'Native opposing-turn closure'):
                delivery.audit(self.case, self.root)

    def test_review_branch_requires_current_pixels_and_originals(self):
        seal = {'provenance_kind': 'native', 'restoration': {'restored': True},
                'sources': {name: delivery.digest(self.root / name)
                            for name in delivery.SOURCES}}
        seal_path = self.root / 'capture-seal.json'
        seal_path.write_text(json.dumps(seal))
        (self.root / 'native-exit.json').write_text(json.dumps({
            'event': 'native_exit', 'capture_seal_sha256': delivery.digest(seal_path)}))
        review = {
            'case_id': self.case, 'reviewer': 'synthetic unit reviewer',
            'original_sha256': seal['sources'],
            'visible': {label: {'camera': 'overview', 'video_frame': 1,
                                'camera_sha256': delivery.digest(self.root / 'overview.mkv'),
                                'observed': True}
                        for label in ('subject_body', 'opposing_body', 'crossing_area')},
            'physical': {'simultaneous_left_turns_observed': True,
                         'both_turns_completed': True, 'no_contact_observed': True,
                         'crossing_order_reviewed': True},
        }
        review_path = self.root / 'opposing-physical-pixel-review.json'
        review_path.write_text(json.dumps(review))
        with patch.object(delivery.media, 'audit', self._fake_decode):
            result = delivery.audit(self.case, self.root)
        self.assertTrue(result['checks']['physical_completion'])
        review['visible']['subject_body']['camera_sha256'] = 'stale'
        review_path.write_text(json.dumps(review))
        with patch.object(delivery.media, 'audit', self._fake_decode):
            with self.assertRaisesRegex(ValueError, 'pixel review missing'):
                delivery.audit(self.case, self.root)


if __name__ == '__main__':
    unittest.main()
