from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_source_capture import OvertakeSourceRecorder


def actor(identity, x, y, heading, speed):
    transform = NS(location=NS(x=x, y=y),
                   get_forward_vector=lambda: NS(x=heading, y=0))
    vertices = [NS(x=x + dx * heading, y=y + dy, z=z)
                for z in (0, 2) for dx in (-1, 1) for dy in (-.5, .5)]
    box = NS(get_world_vertices=lambda _: vertices)
    return NS(id=identity, bounding_box=box,
              get_transform=lambda: transform,
              get_velocity=lambda: NS(x=speed * heading, y=0))


def road(direction, *, other_road=False):
    def waypoint(location):
        lane_id = 2 if abs(location.y) > 1 else 1
        road_id = 10 if other_road and lane_id == 2 else 9
        return NS(is_junction=False, road_id=road_id, lane_id=lane_id,
                  transform=NS(get_forward_vector=lambda: NS(x=direction, y=0)))
    return NS(get_waypoint=waypoint)


class SourceCaptureTests(unittest.TestCase):
    def test_original_lane_speed_and_body_in_both_directions(self):
        for direction in (1, -1):
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as directory:
                ego = actor(1, 0, 2 * direction, direction, 7)
                other = actor(2, 4 * direction, 0, direction, 3)
                recorder = OvertakeSourceRecorder(directory, ego, other, road(direction))
                first = recorder.append(100, 0.)
                second = recorder.append(101, .05)
                recorder.close()
                self.assertEqual((first['ego_lane_id'], first['other_lane_id']), (2, 1))
                self.assertEqual(first['other_speed_mps'], 3)
                self.assertEqual(len(first['ego_corners']), 4)
                self.assertEqual(second['frame'], 101)
                self.assertEqual(len((Path(directory) / 'participant_footprints.jsonl').read_text().splitlines()), 2)

    def test_reject_cross_road_and_broken_frame_join(self):
        with tempfile.TemporaryDirectory() as directory:
            ego, other = actor(1, 0, 2, 1, 7), actor(2, 4, 0, 1, 3)
            recorder = OvertakeSourceRecorder(directory, ego, other, road(1, other_road=True))
            with self.assertRaisesRegex(ValueError, 'same-road'):
                recorder.append(100, 0.)
            recorder.close()
        with tempfile.TemporaryDirectory() as directory:
            recorder = OvertakeSourceRecorder(directory, ego, other, road(1))
            recorder.append(100, 0.)
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(102, .1)
            recorder.close()


if __name__ == '__main__':
    unittest.main()
