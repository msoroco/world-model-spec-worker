"""Saved pixel-review joins and tamper rejection on synthetic inputs."""
import json
import tempfile
import unittest
from pathlib import Path
from pixel_visibility import measure, verify


def rows(path, items):
    path.write_text(''.join(json.dumps(item)+'\n' for item in items))


class PixelReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        self.samples = folder/'native_samples.jsonl'
        self.mapping = folder/'video_frames.jsonl'
        self.video = folder/'approach.mkv'
        self.review = folder/'pixel_review.jsonl'
        self.audit = folder/'pixel_audit.json'
        rows(self.samples, [{'native_frame': 100+i, 'time_s': (i+1)/20,
                             'native_center_xy_m': [-40+10*i, -1.75]} for i in range(4)])
        rows(self.mapping, [{'video_frame': i, 'native_frame': 100+i,
                             'time_s': (i+1)/20} for i in range(4)])
        rows(self.review, [{'video_frame': i, 'native_frame': 100+i,
                            'body_visible': True, 'centerline_visible': i == 2}
                           for i in (1,2,3)])
        self.video.write_bytes(b'synthetic video digest source')
        self.refresh()

    def refresh(self):
        self.audit.write_text(json.dumps(measure(self.samples, self.mapping,
                                                 self.video, self.review)))

    def test_complete_approach_review_and_source_hashes(self):
        value = verify(self.audit, self.samples)
        self.assertEqual((value['body_and_centerline_visible_frames'],
                          value['approach_frames']), (1,3))
        self.video.write_bytes(b'changed video')
        with self.assertRaisesRegex(ValueError, 'source or count mismatch'):
            verify(self.audit, self.samples)

    def test_missing_review_row_and_frame_mismatch_reject(self):
        original = self.review.read_text().splitlines()
        self.review.write_text('\n'.join(original[:-1])+'\n')
        with self.assertRaisesRegex(ValueError, 'cover every approach frame'):
            measure(self.samples, self.mapping, self.video, self.review)
        self.review.write_text('\n'.join(original)+'\n')
        mapping = [json.loads(line) for line in self.mapping.read_text().splitlines()]
        mapping[2]['native_frame'] += 1
        rows(self.mapping, mapping)
        with self.assertRaisesRegex(ValueError, 'frame identity mismatch'):
            measure(self.samples, self.mapping, self.video, self.review)


if __name__ == '__main__':
    unittest.main()
