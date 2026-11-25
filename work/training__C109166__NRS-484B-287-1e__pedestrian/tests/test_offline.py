import json
from pathlib import Path
import tempfile
import unittest
from runner import check
from finalize import diagonal_entry_measurement
HERE = Path(__file__).resolve().parent.parent
class ExactDiagonalOffline(unittest.TestCase):
    def test_exact_runner(self):
        cfg = json.loads((HERE/'config.json').read_text())
        value = check(cfg)
        self.assertEqual(value['frames'], 600)
        self.assertEqual(value['camera_count'], 4)
        self.assertFalse(value['native_executed'])
    def test_missing_original_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing required source: video_frames.jsonl'):
                diagonal_entry_measurement(Path(tmp))
