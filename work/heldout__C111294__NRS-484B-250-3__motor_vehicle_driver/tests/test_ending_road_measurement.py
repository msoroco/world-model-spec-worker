import json
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
from ending_road_measurement import measure


def box(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class EndingRoadMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.topology = {
            'highway_identity_source': 'retained Native/OpenDRIVE lane chain and reviewed highway identity',
            'junction_id': 'J', 'subject_approach_lane': 'S',
            'other_approach_lane': 'T', 'subject_id': 'ending', 'other_id': 'through',
            'conflict_polygon_xy': box(0, 4, 0, 4),
            'lanes': {
                'S': {'junction_id': 'J', 'highway_id': 'ending_road', 'successors': ['C']},
                'C': {'junction_id': None, 'highway_id': 'through_road', 'successors': []},
                'T': {'junction_id': 'J', 'highway_id': 'through_road', 'successors': ['U']},
                'U': {'junction_id': None, 'highway_id': 'through_road', 'successors': []},
            },
        }

    def write(self, subject_positions, other_positions):
        (self.root / 'intersection_topology.json').write_text(json.dumps(self.topology))
        rows = []
        for index, (subject, other) in enumerate(zip(subject_positions, other_positions)):
            rows.append({'frame': 70 + index, 'time_s': index / 20,
                         'subject_id': 'ending', 'other_id': 'through',
                         'subject_corners': box(subject, subject + 1, 1, 2),
                         'other_corners': box(1, 2, other, other + 1)})
        (self.root / 'intersection_participants.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in rows))

    def test_measures_entry_order_and_retains_legal_uncertainty(self):
        self.write([-3, -3, 1, 5], [-3, 1, 5, 6])
        result = measure(self.root / 'intersection_topology.json',
                         self.root / 'intersection_participants.jsonl')
        self.assertTrue(result['subject_entered_after_other_last_conflict_frame'])
        self.assertEqual(result['entry_delta_s'], .05)
        self.assertFalse(result['conflict_overlap_observed'])
        self.assertIsNone(result['approximately_same_time_legal_judgment'])

    def test_detects_simultaneous_body_conflict(self):
        self.write([-3, 1, 5], [-3, 1, 5])
        result = measure(self.root / 'intersection_topology.json',
                         self.root / 'intersection_participants.jsonl')
        self.assertTrue(result['conflict_overlap_observed'])
        self.assertFalse(result['subject_entered_after_other_last_conflict_frame'])

    def test_traverses_source_backed_junction_lanes_to_exterior_highways(self):
        for start, interior, exterior in (('S', 'JS', 'C'), ('T', 'JT', 'U')):
            self.topology['lanes'][start]['junction_id'] = None
            self.topology['lanes'][start]['successors'] = [interior]
            self.topology['lanes'][interior] = {
                'junction_id': 'J',
                'highway_id': self.topology['lanes'][start]['highway_id'],
                'successors': [exterior],
            }
        self.write([-3, 1, 5], [-3, 1, 5])
        result = measure(self.root / 'intersection_topology.json',
                         self.root / 'intersection_participants.jsonl')
        self.assertEqual(result['approaches']['subject']['exterior_lanes'], ['C'])
        self.assertTrue(result['approaches']['other']['continues_beyond_junction'])
        self.topology['lanes']['JT']['successors'] = ['missing']
        (self.root / 'intersection_topology.json').write_text(json.dumps(self.topology))
        with self.assertRaisesRegex(ValueError, 'absent from topology'):
            measure(self.root / 'intersection_topology.json',
                    self.root / 'intersection_participants.jsonl')

    def test_rejects_falsely_declared_ending_road_and_bad_frame_join(self):
        self.write([-3, 1, 5], [-3, 1, 5])
        self.topology['lanes']['C']['highway_id'] = 'ending_road'
        (self.root / 'intersection_topology.json').write_text(json.dumps(self.topology))
        with self.assertRaisesRegex(ValueError, 'does not end'):
            measure(self.root / 'intersection_topology.json',
                    self.root / 'intersection_participants.jsonl')
        self.topology['lanes']['C']['highway_id'] = 'through_road'
        (self.root / 'intersection_topology.json').write_text(json.dumps(self.topology))
        frames = self.root / 'intersection_participants.jsonl'
        rows = [json.loads(line) for line in frames.read_text().splitlines()]
        rows[1]['time_s'] = .2
        frames.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            measure(self.root / 'intersection_topology.json', frames)

    def test_rejects_nonfinite_original_polygon_and_skipped_frame(self):
        self.write([-3, 1, 5], [-3, 1, 5])
        frames = self.root / 'intersection_participants.jsonl'
        rows = [json.loads(line) for line in frames.read_text().splitlines()]
        rows[1]['subject_corners'][0][0] = float('nan')
        frames.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'Nonfinite original polygon'):
            measure(self.root / 'intersection_topology.json', frames)
        self.write([-3, 1, 5], [-3, 1, 5])
        rows = [json.loads(line) for line in frames.read_text().splitlines()]
        rows[2]['frame'] += 1
        frames.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            measure(self.root / 'intersection_topology.json', frames)


if __name__ == '__main__':
    unittest.main()
