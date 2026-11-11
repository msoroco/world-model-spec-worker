import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exposure_source_capture import ExposureSourceRecorder
from endangerment_measurement import measure


def actor(identity, x, speed):
    # Deliberately scrambled native vertex order; recorder must produce a polygon.
    vertices = [NS(x=x + dx, y=dy, z=z) for z in (0, 1)
                for dx, dy in ((-.5, -.5), (.5, .5), (.5, -.5), (-.5, .5))]
    return NS(id=identity, bounding_box=NS(get_world_vertices=lambda _: vertices),
              get_transform=lambda: object(),
              get_velocity=lambda: NS(x=speed, y=0))


class NativeExposureSourceTests(unittest.TestCase):
    def test_original_source_feeds_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = ExposureSourceRecorder(directory, actor(1, 0, 4),
                                              actor(2, 3, 0), 'pedestrian')
            recorder.append(20, 1.0)
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(22, 1.05)
            recorder.append(21, 1.05)
            recorder.close()
            rows = [json.loads(line) for line in
                    (Path(directory) / 'exposed_actor_footprints.jsonl').read_text().splitlines()]
            self.assertEqual([item['frame'] for item in rows], [20, 21])
            report = measure(Path(directory) / 'exposed_actor_footprints.jsonl')
            self.assertAlmostEqual(report['minimum_surface_gap_m'], 2)
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                ExposureSourceRecorder(directory, actor(1, 0, 4), actor(2, 3, 0), 'pedestrian')


if __name__ == '__main__':
    unittest.main()
