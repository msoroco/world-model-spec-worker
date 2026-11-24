import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import saved_comparison as audit
from test_saved_measurement import fixture, write_data

PLAN = ROOT / 'case-plan.json'
CLEAR = ROOT / 'scenes' / 'destination_clear_absent.json'
OCCUPIED = ROOT / 'scenes' / 'destination_occupied_absent.json'


def make_pair(root):
    left, right = root / 'clear', root / 'occupied'
    left.mkdir()
    right.mkdir()
    left_data, left_index = fixture(left)
    right_data, right_index = fixture(right)
    left_index['case_id'] = json.loads(CLEAR.read_text())['case_id']
    left_index['scene_sha256'] = hashlib.sha256(CLEAR.read_bytes()).hexdigest()
    left_data['exception_review']['case_id'] = left_index['case_id']
    left_data['pedestrian'] = [dict(row, body_center_xy_m=[3, 2]) for row in left_data['pedestrian']]
    write_data(left, left_data, left_index, 'exception_review')
    write_data(left, left_data, left_index, 'pedestrian')
    return (left, left_data, left_index), (right, right_data, right_index)


class SavedComparisonTests(unittest.TestCase):
    def compare(self, left, right, root):
        return audit.audit_pair(PLAN, 'destination_half_occupancy', left, CLEAR,
                                right, OCCUPIED, root / 'comparison.json')

    def test_reprocesses_two_sealed_original_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (left, _, _), (right, _, _) = make_pair(root)
            result = self.compare(left, right, root)
            self.assertEqual(result['measured_values'], [0, 600])
            self.assertFalse(result['physical_source_verified'])
            self.assertEqual(result['legal_judgment'], 'unresolved')

    def test_rejects_reused_attempt_and_changed_fixed_site(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (left, left_data, left_index), (right, _, _) = make_pair(root)
            with self.assertRaisesRegex(audit.ComparisonError, 'distinct original attempts'):
                self.compare(left, left, root)
            left_data['site']['intersection_id'] = 'other-intersection'
            write_data(left, left_data, left_index, 'site')
            with self.assertRaisesRegex(audit.ComparisonError, 'fixed original site'):
                self.compare(left, right, root)

    def test_rejects_changed_ego_and_absent_measured_difference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (left, left_data, left_index), (right, _, _) = make_pair(root)
            left_data['ego'][10]['brake'] = False
            write_data(left, left_data, left_index, 'ego')
            with self.assertRaisesRegex(audit.ComparisonError, 'fixed original ego'):
                self.compare(left, right, root)
            left_data['ego'][10]['brake'] = True
            write_data(left, left_data, left_index, 'ego')
            left_data['pedestrian'] = [dict(row, body_center_xy_m=[1, 2]) for row in left_data['pedestrian']]
            write_data(left, left_data, left_index, 'pedestrian')
            with self.assertRaisesRegex(audit.ComparisonError, 'variable did not differ'):
                self.compare(left, right, root)

    def test_rejects_source_hash_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (left, _, _), (right, _, _) = make_pair(root)
            (left / 'pedestrian.json').write_text('[]')
            with self.assertRaisesRegex(Exception, 'hash mismatch'):
                self.compare(left, right, root)


if __name__ == '__main__':
    unittest.main()

class DeviceComparisonTests(unittest.TestCase):
    def test_absent_versus_nonoperating_uses_original_device_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            left, right = root / 'absent', root / 'nonoperating'
            left.mkdir()
            right.mkdir()
            fixture(left)
            data, index = fixture(right)
            scene = ROOT / 'scenes' / 'destination_occupied_nonoperating.json'
            index['case_id'] = json.loads(scene.read_text())['case_id']
            index['scene_sha256'] = hashlib.sha256(scene.read_bytes()).hexdigest()
            data['exception_review']['case_id'] = index['case_id']
            data['site']['official_devices']['entries'] = [{
                'official': True, 'relevant': True, 'source_ref': 'native/device.jsonl',
                'state_by_frame': {str(i): 'not_operating' for i in range(600)}}]
            write_data(right, data, index, 'site')
            write_data(right, data, index, 'exception_review')
            result = audit.audit_pair(PLAN, 'device_absent_or_nonoperating', left, OCCUPIED,
                                      right, scene, root / 'pair.json')
            self.assertEqual(result['measured_values'], ['absent', 'not_operating'])
            data['site']['intersection_id'] = 'wrong'
            write_data(right, data, index, 'site')
            with self.assertRaisesRegex(audit.ComparisonError, 'fixed original site'):
                audit.audit_pair(PLAN, 'device_absent_or_nonoperating', left, OCCUPIED,
                                 right, scene, root / 'pair.json')
