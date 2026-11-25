"""Exercise the original capture closure protocol on an isolated CPU source tree."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit


class CaptureSealTest(unittest.TestCase):
    def test_restored_capture_has_seal_before_native_exit(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            root = Path(tmp)
            for name, content in {
                'construction.json': '{}\n', 'runner.py': 'pass\n',
                'trace.jsonl': '{"frame":1}\n',
                'video_frames.jsonl': '{"carla_frame":1}\n',
                'native-capture-report.json': '{"restored":true}\n',
                'acquisition-provenance.json': '{"diagnostic_fixture":false}\n',
            }.items():
                (root / name).write_text(content)
            with self.assertRaisesRegex(ValueError, 'verified restoration'):
                seal_capture(root, frames=1, restoration={'restored': False}, errors=[])
            self.assertFalse((root / 'capture-seal.json').exists())
            receipt = seal_capture(root, frames=1, restoration={'restored': True},
                                   errors=[], encoder_exit_codes={'overview': 0})
            self.assertEqual(receipt['events'], [
                'capture_finished', 'encoders_closed', 'restoration_verified'])
            self.assertIn('native-capture-report.json', receipt['sources'])
            exit_receipt = record_native_exit(root)
            self.assertEqual(exit_receipt['event'], 'native_exit')
            self.assertFalse(exit_receipt.get('capture_failed', False))
            self.assertEqual(json.loads((root / 'capture-seal.json').read_text())['frames'], 1)


if __name__ == '__main__':
    unittest.main()
