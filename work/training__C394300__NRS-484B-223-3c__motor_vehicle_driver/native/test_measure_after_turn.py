"""Synthetic CPU diagnostics for the unselected NRS 484B.223(3)(c) draft."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from measure_after_turn import measure

GEOMETRY = {
    'center_turn_lane_native_xy_bounds_m': [-66.5, -1.75, 100, 1.75],
    'through_lane_native_xy_bounds_m': [-66.5, 1.75, 100, 5.25],
    'inbound_road_id': 4,
    'inbound_lane_native_xy_bounds_m': [-73.5, 0, -70, 50],
    'center_turn_lane_native_id': -1,
    'through_lane_native_id': -2,
    'left_turn_connector_road_id': 13,
    'highway_road_id': 1,
    'highway_forward_native_xy': [1, 0],
    'native_center_lane_design_verified': False,
}


def row(frame, x, y, road=1, lane=-1, heading=(1, 0)):
    return {'native_frame': frame, 'time_s': frame / 20,
            'native_center_xy_m': [x, y], 'native_forward_xy': list(heading),
            'native_road_id': road, 'native_lane_id': lane,
            'native_body_xy_m': [[x-1, y-.5], [x+1, y-.5],
                                 [x+1, y+.5], [x-1, y+.5]]}


def fixture(target_ft):
    target_m = target_ft * .3048
    # Keep all controls and Native context fixed. Vary only longitudinal
    # distance from turn completion to first contact with the through lane.
    rows = [row(0, -66.6, 0, road=13, heading=(0, -1)), row(1, -66.5, 0)]
    for n in range(1,11):
        rows.append(row(len(rows), -66.5+n*.1, 0))
    completion_x=-65.5
    steps = round(target_m / .1)
    for n in range(1, steps + 1):
        rows.append(row(len(rows), completion_x + n * .1, 0))
    x = completion_x + steps * .1
    rows.append(row(len(rows), x, 1.3))  # first body overlap of through lane
    rows.append(row(len(rows), x, 1.5))
    rows.append(row(len(rows), x, 3.5, lane=-2))
    return rows


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.geometry = self.root/'geometry.json'
        self.samples = self.root/'native-samples.jsonl'
        self.geometry.write_text(json.dumps(GEOMETRY))

    def run_rows(self, rows):
        self.samples.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return measure(self.samples, self.geometry)

    def test_controlled_threshold_probes(self):
        expected = {45: 'within_50_feet', 50: 'unresolved_at_50_feet',
                    55: 'exceeds_50_feet'}
        for feet, relation in expected.items():
            with self.subTest(feet=feet):
                result = self.run_rows(fixture(feet))
                self.assertEqual(result['threshold_relation'], relation)
                self.assertFalse(result['native_center_lane_design_verified'])
                self.assertEqual(len(result['source_hashes']), 2)
                self.assertLessEqual(result['distance_interval_m'][0],
                                     result['sampled_distance_m'])
                self.assertGreaterEqual(result['distance_interval_m'][1],
                                        result['sampled_distance_m'])

    def test_missing_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source missing'):
            measure(self.samples, self.geometry)

    def test_wrong_turn_direction_rejected(self):
        rows = fixture(45)
        rows[0]['native_forward_xy'] = [0, 1]
        with self.assertRaisesRegex(ValueError, 'left turn'):
            self.run_rows(rows)

    def test_turn_transition_precedes_full_body_completion(self):
        result=self.run_rows(fixture(45))
        self.assertEqual(result['left_turn_road_transition_frame_bracket'],[0,1])
        self.assertGreater(result['turn_completion_frame_bracket'][1],1)

    def test_missing_merge_rejected(self):
        rows = fixture(45)[:-3]
        with self.assertRaisesRegex(ValueError, 'merge onset'):
            self.run_rows(rows)

    def test_missing_complete_merge_rejected(self):
        rows = fixture(45)[:-1]
        with self.assertRaisesRegex(ValueError, 'Full-body merge'):
            self.run_rows(rows)

    def test_interrupted_center_lane_rejected(self):
        rows = fixture(45)
        rows[10]['native_lane_id'] = -2
        with self.assertRaisesRegex(ValueError, 'Continuous center-lane'):
            self.run_rows(rows)

    def test_nonmonotone_native_frame_rejected(self):
        rows = fixture(45)
        rows[10]['native_frame'] = rows[9]['native_frame']
        with self.assertRaisesRegex(ValueError, 'order invalid'):
            self.run_rows(rows)

    def test_bad_native_geometry_rejected(self):
        bad = dict(GEOMETRY, through_lane_native_id=-1)
        self.geometry.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.run_rows(fixture(45))


if __name__ == '__main__':
    unittest.main()
