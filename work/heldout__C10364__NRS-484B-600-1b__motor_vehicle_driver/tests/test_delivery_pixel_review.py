"""Reject missing, stale and incomplete Native pixel review claims."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'delivery_audit.py'
SPEC = importlib.util.spec_from_file_location('alley_delivery_audit', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PixelReviewTests(unittest.TestCase):
    def test_requires_source_bound_marks_for_every_participant(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cameras = {'overview': {'sha256': 'a' * 64}}
            with self.assertRaisesRegex(ValueError, 'review is missing'):
                MODULE._visibility(root, 'case', 4, cameras)
            marks = {name: {'camera': 'overview', 'camera_sha256': 'a' * 64,
                            'video_frame': 1, 'visible': True}
                     for name in ('ego', 'pedestrian', 'property')}
            path = root / 'participant-visibility-review.json'
            path.write_text(json.dumps({'case_id': 'case', 'reviewer': 'independent-reviewer',
                                        'visible_participants': marks}))
            self.assertEqual(MODULE._visibility(root, 'case', 4, cameras)['sha256'], MODULE.digest(path))
            marks['property']['camera_sha256'] = 'b' * 64
            path.write_text(json.dumps({'case_id': 'case', 'reviewer': 'independent-reviewer',
                                        'visible_participants': marks}))
            with self.assertRaisesRegex(ValueError, 'property'):
                MODULE._visibility(root, 'case', 4, cameras)


if __name__ == '__main__':
    unittest.main()
