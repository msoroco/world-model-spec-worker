import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from review_originals import inventory


class OriginalReviewTests(unittest.TestCase):
    def test_source_identity_requires_present_matching_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source.bin'
            source.write_bytes(b'original')
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            metadata = root / 'metadata.json'
            data = {'recording_id': 'recording', 'case_id': 'case',
                    'acceptance': {'trace_source': str(source), 'trace_sha256': expected,
                                   'video_source': str(source), 'video_sha256': expected,
                                   'delivery_audit': str(source),
                                   'delivery_audit_sha256': expected}}
            metadata.write_text(json.dumps(data) + '\n')
            self.assertTrue(inventory(metadata)['source_review_complete'])
            source.write_bytes(b'altered')
            self.assertFalse(inventory(metadata)['source_review_complete'])
            source.unlink()
            entry = inventory(metadata)
            self.assertFalse(entry['source_review_complete'])
            self.assertTrue(all(not row['present'] for row in entry['sources']))


if __name__ == '__main__':
    unittest.main()
