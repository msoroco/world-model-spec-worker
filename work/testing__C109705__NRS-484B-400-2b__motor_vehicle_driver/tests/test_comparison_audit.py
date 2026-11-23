import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('comparison_audit', Path(__file__).resolve().parents[1] / 'comparison_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.map = self.root / 'map.json'
        self.map.write_text('{"fixed":"original map"}\n')
        self.map_sha = hashlib.sha256(self.map.read_bytes()).hexdigest()
        self.near = self._report('near', 0.8)
        self.far = self._report('far', 2.8)

    def tearDown(self):
        self.temp.cleanup()

    def _report(self, name, minimum):
        trace = self.root / f'{name}-trace.json'
        trace.write_text(json.dumps({'original': name}) + '\n')
        report = {
            'case_id': name, 'centerline_kind': 'mapped',
            'statutory_position_judgment': None,
            'sample_count': 1, 'per_frame': [{'frame': 50}],
            'approach_road_id': 1, 'destination_road_id': 4,
            'observed_right_min_m': minimum,
            'observed_right_max_m': minimum + 2,
            'sources': [
                {'path':str(self.map), 'sha256':self.map_sha},
                {'path':str(trace), 'sha256':hashlib.sha256(trace.read_bytes()).hexdigest()},
            ],
        }
        path = self.root / f'{name}-report.json'
        path.write_text(json.dumps(report) + '\n')
        return path

    def _audit(self):
        return module.audit(self.near, self.far, expected_near='near', expected_far='far', expected_centerline_kind='mapped')

    def test_source_bound_order_and_no_judgment(self):
        self.assertIsNone(self._audit()['statutory_judgment'])

    def test_bad_hash_and_context_rejected(self):
        self.map.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            self._audit()
        self.map.write_text('{"fixed":"original map"}\n')
        far = json.loads(self.far.read_text())
        far['destination_road_id'] = 9
        self.far.write_text(json.dumps(far) + '\n')
        with self.assertRaisesRegex(ValueError, 'road connection changed'):
            self._audit()

    def test_unrealized_difference_rejected(self):
        far = json.loads(self.far.read_text())
        far['observed_right_min_m'] = 0.2
        self.far.write_text(json.dumps(far) + '\n')
        with self.assertRaisesRegex(ValueError, 'did not measure farther'):
            self._audit()

    def test_legal_label_rejected(self):
        far = json.loads(self.far.read_text())
        far['statutory_position_judgment'] = 'compliant'
        self.far.write_text(json.dumps(far) + '\n')
        with self.assertRaisesRegex(ValueError, 'legal judgment'):
            self._audit()


if __name__ == '__main__':
    unittest.main()
