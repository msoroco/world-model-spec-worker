import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from highway_continuity_finalizer import analyze, build_result
from highway_continuity_source import topology_from_pair
from categorical_highway_points import select_controlled_pair
from test_categorical_highway_points import Point, native_map


class HighwayContinuityFinalizerTests(unittest.TestCase):
    def fixture(self, root):
        world, ending, through = native_map(subject_continues=False)
        continuing = [Point(-8, 4, 1, 0, 7), Point(0, 4, 1, 0, 8, True),
                      Point(6, 4, 1, 0, 7)]
        for first, second in zip(continuing, continuing[1:]):
            first.successors = [second]
        starts = {id(path[0].transform.location): path[0]
                  for path in (ending, continuing, through)}
        world.get_spawn_points = lambda: [NS(location=path[0].transform.location)
                                          for path in (ending, continuing, through)]
        world.get_waypoint = lambda location: starts[id(location)]
        pair = select_controlled_pair(world)
        topology = topology_from_pair(pair, 'continuing', NS(id=11), NS(id=12),
                                      [[-2, -2], [2, -2], [2, 2], [-2, 2]])
        (root / 'highway_pair_topology.json').write_text(json.dumps(topology))
        (root / 'config.json').write_text((ROOT / 'config-highway-continuing.json').read_text())
        (root / 'control_inventory.json').write_text(json.dumps({
            'format': 'worker-ending-road-original-control-inventory',
            'junction_id': pair['junction_id'],
            'ending_landmarks': [], 'through_landmarks': [], 'junction_lights': []}))
        def box(x, y):
            return [[x-.5, y-.5], [x+.5, y-.5],
                    [x+.5, y+.5], [x-.5, y+.5]]
        participants, traces, maps = [], [], []
        for i, (x, y) in enumerate([(-5, -5), (0, 0), (5, 5)]):
            frame, time_s = 100+i, .05*i
            participants.append({'frame': frame, 'time_s': time_s,
                                 'subject_id': '11', 'other_id': '12',
                                 'subject_corners': box(x, 0), 'other_corners': box(0, y)})
            traces.append({'frame': frame, 'time_s': time_s})
            maps.append({'video_frame': i, 'carla_frame': frame, 'time_s': time_s})
        for filename, rows in (('intersection_participants.jsonl', participants),
                               ('trace.jsonl', traces), ('video_frames.jsonl', maps)):
            (root / filename).write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def test_source_bound_analysis_and_stale_frame_rejection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            report = analyze(root)
            self.assertEqual(report['measurements']['highway_continuity_observation']
                             ['value']['subject_entry_frame'], 101)
            result = build_result(root, report)
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertTrue((root / 'intersection_occupancy.jsonl').is_file())
            rows = (root / 'video_frames.jsonl').read_text().splitlines()
            first = json.loads(rows[0]); first['carla_frame'] = 99
            rows[0] = json.dumps(first)
            (root / 'video_frames.jsonl').write_text('\n'.join(rows)+'\n')
            with self.assertRaisesRegex(ValueError, 'source/frame-map join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
