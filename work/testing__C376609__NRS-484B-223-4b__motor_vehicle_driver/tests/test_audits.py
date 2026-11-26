"""Diagnostic protocol tests; no original-source or physical acceptance claim."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import audit as compare
from delivery_audit import audit as delivery

PLAN = json.loads((HERE / 'case-plan.json').read_text())


class AuditProtocolTests(unittest.TestCase):
    def synthetic_pair(self, spec):
        rows = {}
        for index, case in enumerate(spec['case_ids']):
            rows[case] = {
                'format': 'worker-independent-original-delivery-measurement',
                'case_id': case, 'frame_count': 900, 'full_video_decode': True,
                'diagnostic_fixture': True, 'source_verified': False,
                'public_highway_source_sha256': 'diagnostic-only',
                'driver_actor_id': 'diagnostic-driver', 'vehicle_blueprint': 'diagnostic-vehicle',
                'camera_plan_sha256': 'diagnostic-camera', 'duration_frames': 900,
                'map_sha256': 'diagnostic-map', 'result_sha256': 'diagnostic-result-' + str(index),
                'observables': {name: index for name in spec['deliberate_differences']},
            }
        return rows

    def test_all_eight_diagnostic_comparison_protocols(self):
        self.assertEqual(len(PLAN['comparisons']), 8)
        for spec in PLAN['comparisons']:
            with self.subTest(spec=spec['comparison_id']):
                result = compare(PLAN, spec['comparison_id'], self.synthetic_pair(spec), diagnostic=True)
                self.assertFalse(result['source_verified'])
                self.assertIsNone(result['legal_verdict'])

    def test_original_comparison_rejects_diagnostic_source(self):
        spec = PLAN['comparisons'][0]
        with self.assertRaisesRegex(ValueError, 'diagnostic/original provenance'):
            compare(PLAN, spec['comparison_id'], self.synthetic_pair(spec))

    def test_comparison_rejects_changed_fixed_condition(self):
        spec = PLAN['comparisons'][0]
        rows = self.synthetic_pair(spec)
        rows[spec['case_ids'][1]]['driver_actor_id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'fixed comparison condition'):
            compare(PLAN, spec['comparison_id'], rows, diagnostic=True)

    def test_delivery_rejects_missing_original_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            case = PLAN['cases'][0]['case_id']
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                delivery(case, root, root / 'pixel-review.json', root / 'physical.json')


if __name__ == '__main__':
    unittest.main()
