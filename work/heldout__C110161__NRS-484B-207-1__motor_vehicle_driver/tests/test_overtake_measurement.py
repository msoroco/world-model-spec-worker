import json
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
from overtake_measurement import measure


def box(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class OvertakeMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'participant_footprints.jsonl'

    def write(self, return_x=12, other_heading=(1, 0)):
        rows = []
        for i, (ego_x, ego_y) in enumerate(((0, 4), (5, 4), (10, 4), (return_x, 2))):
            rows.append({'frame': 100 + i, 'time_s': i / 20,
                         'ego_id': 'ego', 'other_id': 'other',
                         'road_tangent_xy': [1, 0], 'ego_heading_xy': [1, 0],
                         'other_heading_xy': list(other_heading),
                         'ego_corners': box(ego_x, ego_x + 4, ego_y, ego_y + 2),
                         'other_corners': box(5, 9, 0, 2)})
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def test_left_pass_and_measured_rightward_return(self):
        self.write()
        result = measure(self.path)
        self.assertTrue(result['all_abreast_left'])
        self.assertEqual(result['min_abreast_lateral_gap_m'], 2)
        self.assertEqual(result['first_return_frame'], 103)
        self.assertEqual(result['clearance_at_first_return_m'], 3)
        self.assertFalse(result['legal_acceptance_claimed'])

    def test_rejects_opposing_direction_and_incomplete_trace(self):
        self.write(other_heading=(-1, 0))
        with self.assertRaisesRegex(ValueError, 'same direction'):
            measure(self.path)
        self.write(return_x=8)
        self.assertEqual(measure(self.path)['clearance_at_first_return_m'], -1)

    def test_rejects_changed_identity_and_frame_gap(self):
        self.write()
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        rows[2]['other_id'] = 'replaced'
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure(self.path)
        rows[2]['other_id'] = 'other'
        rows[2]['time_s'] += .1
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            measure(self.path)

    def test_rejects_nonfinite_geometry_and_skipped_native_frame(self):
        self.write()
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        rows[1]['ego_corners'][0][0] = float('nan')
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'Nonfinite original footprint'):
            measure(self.path)
        self.write()
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        rows[2]['frame'] += 10
        rows[3]['frame'] += 10
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            measure(self.path)


if __name__ == '__main__':
    unittest.main()
