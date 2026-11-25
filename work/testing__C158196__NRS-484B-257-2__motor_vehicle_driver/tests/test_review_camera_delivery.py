import json
from pathlib import Path
import tempfile
import unittest

import original_camera_review
import review_camera_delivery


class IndependentCameraReviewTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        self.attempt = Path(self.private.name)
        (self.attempt / 'channels').mkdir()
        rows = [
            {'video_frame': index, 'carla_frame': 100 + index,
             'time_s': 5 + index * 0.05,
             'camera_frames': {name: 100 + index for name in original_camera_review.CAMERAS}}
            for index in range(2)]
        (self.attempt / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in rows))
        for name in original_camera_review.CAMERAS:
            (self.attempt / (name + '.mkv')).write_bytes(name.encode())
        names = ['video_frames.jsonl', *(name + '.mkv' for name in original_camera_review.CAMERAS)]
        hashes = {name: review_camera_delivery.sha(self.attempt / name) for name in names}
        original_camera_review.write(self.attempt, rows, hashes,
                                     self.attempt / 'channels/original_camera_review.json')

    def test_independent_review_source_and_frame_bindings(self):
        receipt = review_camera_delivery.audit(self.attempt)
        self.assertEqual(receipt['frame_count'], 2)
        self.assertTrue(receipt['software_audit_passed'])
        (self.attempt / 'approach.mkv').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source differs'):
            review_camera_delivery.audit(self.attempt)

    def test_rejects_changed_derived_frame_identity(self):
        path = self.attempt / 'channels/original_camera_review.json'
        data = json.loads(path.read_text())
        data['original_camera_review']['frame_index'][1]['carla_frame'] = 999
        path.write_text(json.dumps(data) + '\n')
        with self.assertRaisesRegex(ValueError, 'frame identity differs'):
            review_camera_delivery.audit(self.attempt)


if __name__ == '__main__':
    unittest.main()
