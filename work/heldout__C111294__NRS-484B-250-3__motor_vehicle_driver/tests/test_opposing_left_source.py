import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opposing_left_measurement import measure_opposing_left
from opposing_left_source import context_from_native, OpposingLeftSourceRecorder
import test_opposing_left_route
from opposing_left_route import select_opposing_left_routes


class Actor:
    def __init__(self, actor_id, x, y, dx, dy):
        self.id, self.x, self.y, self.dx, self.dy = actor_id, x, y, dx, dy
        self.bounding_box = NS(get_world_vertices=lambda transform: [
            NS(x=self.x + offset_x, y=self.y + offset_y)
            for offset_x, offset_y in ((-1, -.5), (1, -.5), (1, .5), (-1, .5))])

    def get_transform(self):
        return NS(get_forward_vector=lambda: NS(x=self.dx, y=self.dy))


class OpposingSourceTests(unittest.TestCase):
    def fixture(self, root):
        world, _, _ = test_opposing_left_route.OpposingTests().map()
        selection = select_opposing_left_routes(world)
        turning, opposite = Actor(11, -8, 0, 1, 0), Actor(12, 8, 0, -1, 0)
        context = context_from_native(selection, turning, opposite)
        recorder = OpposingLeftSourceRecorder(root, context, turning, opposite)
        mapping = []
        for index in range(3):
            turning.x += 1
            opposite.x -= 1
            if index == 2:
                turning.dx, turning.dy = 0, 1
            recorder.append(100 + index, index * .05)
            mapping.append({'carla_frame': 100 + index, 'time_s': index * .05})
        recorder.close()
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
        return context

    def test_original_sources_and_measured_turn_are_joined(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = self.fixture(root)
            result = measure_opposing_left(root)
            self.assertEqual(result['value']['frames'], 3)
            self.assertEqual(result['value']['junction_id'], context['junction_id'])
            self.assertAlmostEqual(result['value']['observed_turn_heading_change_rad'], 1.5707963267948966)
            self.assertEqual(len(result['sources']), 3)
            self.assertIsNone(result['value']['turn_physically_completed'])
            with self.assertRaises(FileExistsError):
                OpposingLeftSourceRecorder(root, context, Actor(11, 0, 0, 1, 0),
                                           Actor(12, 0, 0, -1, 0))

    def test_missing_changed_and_skipped_originals_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows_path = root / 'opposing_left_participants.jsonl'
            rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
            rows[1]['opposite_actor_id'] = 'stale'
            rows_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                measure_opposing_left(root)
            rows[1]['opposite_actor_id'] = '12'
            rows[1]['frame'] = 105
            rows_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'frame-map join'):
                measure_opposing_left(root)
            rows_path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure_opposing_left(root)

    def test_disconnected_route_rejected_before_capture(self):
        world, turning_path, _ = test_opposing_left_route.OpposingTests().map()
        selection = select_opposing_left_routes(world)
        turning_path[0].successors = []
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            context_from_native(selection, Actor(11, 0, 0, 1, 0), Actor(12, 0, 0, -1, 0))


if __name__ == '__main__':
    unittest.main()
