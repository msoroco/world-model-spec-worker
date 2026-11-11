import sys
import json
from pathlib import Path
from types import SimpleNamespace as NS
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from categorical_highway_points import select_controlled_pair
from highway_continuity_source import topology_from_pair, measure_originals
from test_categorical_highway_points import Point, native_map


class HighwayContinuitySourceTests(unittest.TestCase):
    def setUp(self):
        world, ending, through = native_map(subject_continues=False)
        continuing = [Point(-8, 4, 1, 0, 7), Point(0, 4, 1, 0, 8, True),
                      Point(6, 4, 1, 0, 7)]
        for first, second in zip(continuing, continuing[1:]):
            first.successors = [second]
        starts = {id(path[0].transform.location): path[0]
                  for path in (ending, through, continuing)}
        world.get_spawn_points = lambda: [NS(location=path[0].transform.location)
                                          for path in (ending, through, continuing)]
        world.get_waypoint = lambda location: starts[id(location)]
        self.pair = select_controlled_pair(world)
        self.polygon = [[-2, -2], [2, -2], [2, 2], [-2, 2]]

    def topology(self, category):
        return topology_from_pair(self.pair, category, NS(id=11), NS(id=12),
                                  self.polygon)

    def test_both_categories_retain_same_other_route_and_all_successors(self):
        ending = self.topology('ending')
        continuing = self.topology('continuing')
        self.assertEqual(ending['routes']['other'], continuing['routes']['other'])
        self.assertEqual(ending['routes']['continuing'], continuing['routes']['continuing'])
        self.assertEqual(ending['routes']['ending'], continuing['routes']['ending'])
        self.assertFalse(ending['legal_highway_classification_claimed'])
        self.assertEqual(continuing['selected_category'], 'continuing')

    def test_disconnected_and_false_through_route_rejected(self):
        self.pair['continuing'][0].successors = []
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            self.topology('continuing')
        self.pair['continuing'][0].successors = [self.pair['continuing'][1]]
        self.pair['other'][-1].road_id = 99
        with self.assertRaisesRegex(ValueError, 'does not continue'):
            self.topology('ending')

    def test_original_body_occupancy_and_missing_topology(self):
        def box(x, y):
            return [[x-.5, y-.5], [x+.5, y-.5],
                    [x+.5, y+.5], [x-.5, y+.5]]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            topology_path = root / 'highway_pair_topology.json'
            participants_path = root / 'intersection_participants.jsonl'
            topology_path.write_text(json.dumps(self.topology('continuing')))
            participants_path.write_text(''.join(json.dumps({
                'frame': 100 + i, 'time_s': .05 * i,
                'subject_id': '11', 'other_id': '12',
                'subject_corners': box(x, 0), 'other_corners': box(0, y)}) + '\n'
                for i, (x, y) in enumerate([(-5, -5), (0, 0), (5, 5)])))
            result = measure_originals(topology_path, participants_path)
            self.assertEqual(result['selected_category'], 'continuing')
            self.assertEqual(result['subject_entry_frame'], 101)
            self.assertFalse(result['legal_highway_classification_claimed'])
            altered = self.topology('continuing')
            false_ending_branch = [dict(row) for row in altered['routes']['ending']]
            false_ending_branch[-1]['road_id'] = false_ending_branch[0]['road_id']
            altered['witness_paths'].append(false_ending_branch)
            topology_path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'branch witnesses contradict ending'):
                measure_originals(topology_path, participants_path)
            topology_path.write_text(json.dumps(self.topology('continuing')))
            rows = participants_path.read_text().splitlines()
            first = json.loads(rows[0]); first['time_s'] = float('nan')
            rows[0] = json.dumps(first)
            participants_path.write_text('\n'.join(rows)+'\n')
            with self.assertRaisesRegex(ValueError, 'frame/time missing'):
                measure_originals(topology_path, participants_path)
            topology_path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure_originals(topology_path, participants_path)


if __name__ == '__main__':
    unittest.main()
