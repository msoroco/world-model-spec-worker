import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_review import prepare
from yield_context import CAMERAS, derive_context


class ReviewTemplateTests(unittest.TestCase):
    def test_template_hashes_sources_but_claims_no_visual_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'video_frames.jsonl').write_text(json.dumps({
                'video_frame': 0, 'carla_frame': 100, 'time_s': 5.})+'\n')
            for name in CAMERAS:
                (root/name).write_bytes(b'cpu-camera-frame')
            template = prepare(root)
            self.assertIsNone(template['no_stop_line'])
            self.assertIsNone(template['yield_sign_face_visible'])
            self.assertEqual(len(template['source_sha256']), 4)
            with self.assertRaisesRegex(ValueError, 'Retain existing'):
                prepare(root)
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                derive_context(root)
