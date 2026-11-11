import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_origin_measurement import measure


def rows(direction=1, outer=False):
    # +y is right for CARLA eastbound travel; a left turn rotates negative.
    headings = ([1, 0], [1, 0], [.94, -.34], [.5, -.866], [0, -1])
    if direction == -1:
        headings = [(-x, -y) for x, y in headings]
    output = []
    for index, heading in enumerate(headings):
        output.append({'frame': 100+index, 'time_s': index*.05,
                       'ego_id': 'native-subject-7', 'ego_forward_xy': list(heading),
                       'is_junction': index >= 2, 'road_id': 17,
                       'lane_id': (2*direction if outer else direction),
                       'center_turn_road_id': 17,
                       'center_turn_lane_id': direction,
                       'designation_source': 'original Native lane-marking inventory plus authored designation',
                       'center_marking_actor_ids': [25, 26]})
    return output


class TurnOriginMeasurementTests(unittest.TestCase):
    def measure_rows(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'turn_origin_native.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in source))
            return measure(path)

    def test_center_and_outer_origins_in_both_approach_directions(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                center = self.measure_rows(rows(direction))
                outer = self.measure_rows(rows(direction, outer=True))
                self.assertTrue(center['origin_matches_center_lane'])
                self.assertFalse(outer['origin_matches_center_lane'])
                self.assertEqual(center['approach_origin_frame'], 101)
                self.assertEqual(center['first_observed_left_frame'], 104)
                self.assertFalse(center['designation_authority_verified'])
                self.assertFalse(center['legal_acceptance_claimed'])

    def test_missing_source_and_discontinuous_frames_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure(Path(directory) / 'turn_origin_native.jsonl')
        bad = rows();bad[2]['frame'] = 900
        with self.assertRaisesRegex(ValueError, 'continuous 20 Hz'):
            self.measure_rows(bad)
        bad = rows();bad[2]['time_s'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'identity/frame/time'):
            self.measure_rows(bad)

    def test_wrong_turn_and_missing_designation_rejected(self):
        bad = rows()
        for row in bad[2:]:row['ego_forward_xy'] = [1, 0]
        with self.assertRaisesRegex(ValueError, 'No observed left deflection'):
            self.measure_rows(bad)
        bad = rows();bad[1]['center_marking_actor_ids'] = []
        with self.assertRaisesRegex(ValueError, 'lacks center-lane designation source'):
            self.measure_rows(bad)

    def test_approach_lane_is_last_nonjunction_sample(self):
        bad = rows();bad[3]['is_junction'] = False
        with self.assertRaisesRegex(ValueError, 'single junction entry'):
            self.measure_rows(bad)


if __name__ == '__main__':
    unittest.main()
