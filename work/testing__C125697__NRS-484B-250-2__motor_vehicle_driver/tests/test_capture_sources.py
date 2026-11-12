import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


capture = module('capture_sources')
measure = module('simultaneous_entries')
pair = module('native_pair')


def at(x, y, yaw):
    return NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))


class Map:
    name = 'TownX'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road is not False:
            raise AssertionError('Original Native waypoint must not be projected')
        road = 2 if abs(location.y) > 6 else 1
        inside = 10 <= location.x <= 20 and -5 <= location.y <= 5
        return NS(road_id=road, lane_id=-1, lane_type='Driving',
                  is_junction=inside, get_junction=lambda: NS(id=44))


class Actor:
    def __init__(self, identifier, x, y, yaw):
        self.id, self.x, self.y, self.yaw = identifier, x, y, yaw
        self.bounding_box = NS(get_world_vertices=lambda pose: [
            NS(x=self.x + dx, y=self.y + dy) for dx, dy in
            ((-1, -1), (-1, 1), (1, 1), (1, -1))])

    def get_transform(self):
        return at(self.x, self.y, self.yaw)

    def get_location(self):
        return self.get_transform().location

    def get_velocity(self):
        return NS(x=2.0, y=0.0, z=0.0)


SITE = {'native_map_name': 'TownX', 'crossing_id': 44,
        'ego_highway_id': 'east-west', 'other_highway_id': 'north-south',
        'crossing_polygon_xy_m': [[10, -5], [20, -5], [20, 5], [10, 5]],
        'crossing_polygon_source': 'reviewed Native junction envelope',
        'approach_geometry_source': 'reviewed waypoints',
        'median_spacing_source': 'reviewed roadway opening',
        'all_entrances_source': 'reviewed affected-lane inventory',
        'signal_governance_source': 'Native affected-lane readback',
        'signal_head_video_source': 'overview and approach source cameras',
        'same_statutory_crossing': True}
TRANSFORMS = {'ego_approach': at(0, 0, 0), 'ego_entry': at(12, 0, 0),
              'other_approach': at(15, -12, 90), 'other_entry': at(15, 0, 90)}


class FrameMap:
    def __init__(self):
        self.rows = []

    def append(self, frame, time_s):
        row = {'video_frame': len(self.rows), 'carla_frame': frame, 'time_s': time_s}
        self.rows.append(row)
        return row


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.plan = pair.plan_pair(Map(), SITE, TRANSFORMS, 'right')
        self.ego, self.other = Actor(1, 0, 0, 0), Actor(2, 15, -12, 90)
        self.light_a, self.light_b = NS(id=17, get_state=lambda: 'Off'), NS(id=18, get_state=lambda: 'Off')

    def record(self, frame_map, stream, frame, time_s, cameras=None, lights=None):
        snapshot = NS(frame=frame, timestamp=NS(elapsed_seconds=time_s))
        cameras = cameras if cameras is not None else {name: frame for name in capture.CAMERAS}
        lights = lights if lights is not None else [self.light_a, self.light_b]
        return capture.record_crossing_sample(frame_map, stream, snapshot, Map(),
                                              self.ego, self.other, lights,
                                              NS(Off='Off'), cameras, self.plan)

    def test_original_capture_feeds_entry_measurement(self):
        frames, stream = FrameMap(), io.StringIO()
        self.record(frames, stream, 100, 1.0)
        self.other.x, self.other.y = 15, 0
        self.record(frames, stream, 101, 1.05)
        self.ego.x = 12
        self.record(frames, stream, 102, 1.1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'crossing_history.jsonl').write_text(stream.getvalue())
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames.rows))
            (root / 'junction_context.json').write_text(json.dumps(capture.junction_context(SITE, self.plan)))
            result = measure.analyze(root)
        self.assertTrue(result['other_spatially_right_of_ego_approach'])
        self.assertAlmostEqual(result['absolute_entry_time_difference_s'], .05)
        self.assertEqual(result['legal_conclusion'], 'unresolved')

    def test_camera_join_and_signal_readback_rejected_before_write(self):
        frames, stream = FrameMap(), io.StringIO()
        bad_camera = {name: 100 for name in capture.CAMERAS}
        bad_camera['approach'] = 101
        with self.assertRaisesRegex(ValueError, 'Four source-camera frames'):
            self.record(frames, stream, 100, 1.0, cameras=bad_camera)
        bad_light = NS(id=18, get_state=lambda: 'Green')
        with self.assertRaisesRegex(ValueError, 'read back Off'):
            self.record(frames, stream, 100, 1.0, lights=[self.light_a, bad_light])
        self.assertFalse(stream.getvalue())
        self.assertFalse(frames.rows)

    def test_incomplete_body_rejected_before_frame_map(self):
        self.other.bounding_box = NS(get_world_vertices=lambda pose: [NS(x=0, y=0)])
        frames, stream = FrameMap(), io.StringIO()
        with self.assertRaisesRegex(ValueError, 'Complete Native body'):
            self.record(frames, stream, 100, 1.0)
        self.assertFalse(frames.rows)


if __name__ == '__main__':
    unittest.main()
