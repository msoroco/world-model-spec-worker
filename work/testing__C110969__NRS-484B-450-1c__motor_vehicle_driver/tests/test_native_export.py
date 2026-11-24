import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from native_acquisition import acquire
from native_export import export
from native_media import NativeMediaWriter
from test_native_acquisition import Actor, BOUNDARY, CASE, Controller, Observer, World
from test_native_media import Cameras


class ExportTests(unittest.TestCase):
    def test_original_pngs_export_losslessly_with_exact_frame_map(self):
        with tempfile.TemporaryDirectory(dir=Path('.runtime-work').resolve()) as temp:
            root = Path(temp)
            acquire(World(), Actor(), BOUNDARY, Controller(), Observer(), CASE,
                    'cpu-export', root, 2, NativeMediaWriter(root, Cameras()))
            proof = export(root, CASE, expected_count=2)
            self.assertEqual(proof['frame_count'], 2)
            self.assertEqual(set(proof['videos']),
                             {'overview','approach','reference_corner','driver_reference'})
            trace = [json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines()]
            mapping = [json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
            self.assertEqual([row['frame'] for row in trace],
                             [row['carla_frame'] for row in mapping])
            with self.assertRaisesRegex(ValueError, 'prior Native export'):
                export(root, CASE, expected_count=2)


if __name__ == '__main__':
    unittest.main()
