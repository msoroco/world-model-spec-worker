import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'right_half_measurement.py'
SPEC = importlib.util.spec_from_file_location('right_half_measurement', MODULE)
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)


def row(frame, direction, body_offsets):
    tangent = [direction, 0]
    right_y = direction
    return {
        'ego_id': 'subject-vehicle-1', 'frame': frame, 'time_s': frame * .05,
        'roadway_center_point_xy': [0, 0], 'travel_tangent_xy': tangent,
        'left_road_edge_xy': [0, -3 * right_y],
        'right_road_edge_xy': [0, 3 * right_y],
        'ego_corners': [[x, offset * right_y] for x, offset in zip((-2, 2, 2, -2), body_offsets)],
    }


class RightHalfMeasurementTest(unittest.TestCase):
    def measure(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'directed_roadway_footprints.jsonl'
            path.write_text(''.join(json.dumps(item) + '\n' for item in rows))
            return measurement.measure(path)

    def test_eastbound_full_body_and_centerline_crossing(self):
        report = self.measure([row(0, 1, [0.2, 0.2, 1.8, 1.8]),
                               row(1, 1, [-0.2, -0.2, 1.8, 1.8])])
        self.assertEqual(report['frames_entirely_right'], [0])
        self.assertEqual(report['frames_crossing_centerline'], [1])
        self.assertAlmostEqual(report['minimum_body_right_offset_m'], -0.2)
        self.assertAlmostEqual(report['minimum_roadway_width_m'], 6)
        self.assertIsNone(report['sufficient_width_legal_judgment'])

    def test_westbound_reverses_right_side(self):
        report = self.measure([row(0, -1, [0, 0, 1.5, 1.5]),
                               row(1, -1, [0.1, 0.1, 1.5, 1.5])])
        self.assertEqual(report['frames_entirely_right'], [0, 1])
        self.assertEqual(report['frames_crossing_centerline'], [])

    def test_rejects_subject_and_frame_join_changes(self):
        bad = row(1, 1, [0, 0, 1, 1])
        bad['ego_id'] = 'different-vehicle'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.measure([row(0, 1, [0, 0, 1, 1]), bad])
        bad['ego_id'] = 'subject-vehicle-1'
        bad['time_s'] = 0.1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            self.measure([row(0, 1, [0, 0, 1, 1]), bad])

    def test_rejects_inverted_directed_edges(self):
        bad = row(1, 1, [0, 0, 1, 1])
        bad['right_road_edge_xy'] = [0, -3]
        with self.assertRaisesRegex(ValueError, 'straddle centerline'):
            self.measure([row(0, 1, [0, 0, 1, 1]), bad])


if __name__ == '__main__':
    unittest.main()
