import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT = 'testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accepted_source_review import review


class AcceptedSourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.evidence = ROOT / 'inputs' / ASSIGNMENT / 'evidence.json'

    def test_all_four_metadata_bound_without_claiming_coverage(self):
        result = review(self.evidence, ROOT)
        self.assertEqual(len(result['records']), 4)
        self.assertEqual(result['physical_coverage_verdict'], 'unresolved')
        self.assertEqual({r['source_review_status'] for r in result['records']},
                         {'original_assets_unavailable'})

    def test_frozen_metadata_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = json.loads(self.evidence.read_text())
            data['recordings'][0]['sources'][0]['sha256'] = '0' * 64
            path = Path(temp) / 'evidence.json'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'metadata hash mismatch'):
                review(path, ROOT)

    def test_available_but_wrong_original_asset_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = json.loads(self.evidence.read_text())
            rid = data['recordings'][0]['recording_id']
            path = Path(temp) / rid / 'trace.json'
            path.parent.mkdir()
            path.write_text('wrong original trace\n')
            with self.assertRaisesRegex(ValueError, 'original asset hash mismatch'):
                review(self.evidence, ROOT, temp)


if __name__ == '__main__':
    unittest.main()
