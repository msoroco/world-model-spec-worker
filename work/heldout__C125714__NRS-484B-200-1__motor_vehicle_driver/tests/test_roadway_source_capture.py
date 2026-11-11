import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from roadway_source_capture import RoadwaySourceRecorder
from test_directed_geometry import lane


class SourceCaptureTests(unittest.TestCase):
    def test_original_rows_and_frame_rejection(self):
        subject = lane(-1, 0, 1.5, 1)
        subject.get_left_lane = lambda: lane(1, 0, -1.5, -1)
        vertices = [NS(x=i % 2, y=-1 + (i // 2) % 2, z=i // 4) for i in range(8)]
        ego = NS(id=19, get_transform=lambda: object(),
                 bounding_box=NS(get_world_vertices=lambda _: vertices))
        with tempfile.TemporaryDirectory() as directory:
            recorder = RoadwaySourceRecorder(directory, ego)
            first = recorder.append(10, .5, subject)
            self.assertEqual(first['ego_id'], '19')
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(12, .55, subject)
            recorder.append(11, .55, subject)
            recorder.close()
            path = Path(directory) / 'directed_roadway_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([row['frame'] for row in rows], [10, 11])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                RoadwaySourceRecorder(directory, ego)


if __name__ == '__main__':
    unittest.main()
