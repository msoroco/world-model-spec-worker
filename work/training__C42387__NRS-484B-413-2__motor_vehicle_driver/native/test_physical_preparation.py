"""Three source-shaped motion outcomes, all explicitly diagnostic fixtures."""
import json
import tempfile
import unittest
from pathlib import Path

from physical_preparation import assess


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class PhysicalRightTurnFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'road_geometry.json').write_text(json.dumps({
            'approach_road_id': 1, 'destination_road_id': 2}) + '\n')
        self.mapping = [{'video_frame': i, 'native_frame': 1000 + i,
                         'time_s': i / 20} for i in range(600)]
        self.samples = [{'native_frame': 1000 + i, 'time_s': i / 20,
                         'road_id': 1 if i < 300 else 2,
                         'ego_heading_deg': 0 if i < 300 else -90}
                        for i in range(600)]
        self.body = [{'frame': 1000 + i, 'time_s': i / 20,
                      'road_id': 1 if i < 300 else 2,
                      'body_vertices_m': [[i * .1 - 1, -1, 0], [i * .1 + 1, -1, 0],
                                          [i * .1 + 1, 1, 0], [i * .1 - 1, 1, 0]]}
                     for i in range(600)]

    def write(self):
        for name, values in [('video_frames.jsonl', self.mapping),
                             ('native_samples.jsonl', self.samples),
                             ('body_history.jsonl', self.body)]:
            write_rows(self.root / name, values)

    def test_complete_motion(self):
        self.write()
        result = assess(self.root)
        self.assertEqual(result['status'], 'met')
        self.assertEqual(result['observed']['first_destination_sample'], 300)
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_incomplete_motion(self):
        for row in self.body:
            row['road_id'] = 1
        for row in self.samples:
            row['road_id'] = 1
        self.write()
        self.assertEqual(assess(self.root)['status'], 'not_met')

    def test_missing_evidence(self):
        self.write()
        (self.root / 'body_history.jsonl').unlink()
        result = assess(self.root)
        self.assertEqual(result['status'], 'unverified')
        self.assertIn('body_history.jsonl', result['missing_evidence'])


if __name__ == '__main__':
    unittest.main()
