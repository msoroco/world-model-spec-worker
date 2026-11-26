"""CPU source-shape tests; no original Native observation is claimed."""
import json
import tempfile
import unittest
from pathlib import Path

from measure_observed import CASE_PREFIX, measure
from saved_measure import process


class ObservedSignalMeter(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / 'native_samples.jsonl'
        self.case = CASE_PREFIX + 'a'
        self.rows = [
            {'provenance': 'synthetic_cpu_fixture', 'case_id': self.case,
             'native_frame': frame, 'sample_index': frame, 'time_s': frame / 20,
             'ego_center_xy_m': [frame * 0.5, 0.0 if frame < 300 else -(frame - 300) * 0.2],
             'ego_heading_deg': 0.0 if frame < 300 else -10.0,
             'ego_speed_mps': 10.0,
             'right_lamp_commanded': frame >= 220,
             'right_lamp_observed': frame >= 220,
             'course_change_observed': frame >= 300,
             'area_classification': 'business_district', 'precipitation': 'rain'}
            for frame in range(600)]

    def write(self):
        self.path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in self.rows))

    def test_measured_40_meters_and_no_legal_verdict(self):
        self.write()
        result = measure(self.path, self.case, allow_fixture=True)
        self.assertEqual(result['continuous_observed_signal_distance_m'], 40.0)
        self.assertTrue(result['business_100ft_distance_observed'])
        self.assertFalse(result['original_native_observed'])
        self.assertIsNone(result['legal_verdict'])

    def test_20_meter_comparison(self):
        for row in self.rows:
            row['right_lamp_commanded'] = row['native_frame'] >= 260
            row['right_lamp_observed'] = row['native_frame'] >= 260
        self.write()
        self.assertEqual(measure(self.path, self.case, allow_fixture=True)
                         ['continuous_observed_signal_distance_m'], 20.0)

    def test_command_does_not_substitute_observed_lamp(self):
        for row in self.rows:
            row.pop('right_lamp_observed')
        self.write()
        with self.assertRaisesRegex(ValueError, 'Observed indicator source missing'):
            measure(self.path, self.case, allow_fixture=True)

    def test_first_frame_lamp_is_censored(self):
        for row in self.rows:
            row['right_lamp_commanded'] = True
            row['right_lamp_observed'] = True
        self.write()
        result = measure(self.path, self.case, allow_fixture=True)
        self.assertIsNone(result['signal_onset_frame'])
        self.assertFalse(result['business_100ft_distance_observed'])

    def test_lamp_gap_restarts_continuous_distance(self):
        self.rows[250]['right_lamp_observed'] = False
        self.write()
        result = measure(self.path, self.case, allow_fixture=True)
        self.assertEqual(result['signal_onset_frame'], 251)
        self.assertEqual(result['continuous_observed_signal_distance_m'], 24.5)

    def test_missing_frame_rejected(self):
        self.rows.pop()
        self.write()
        with self.assertRaisesRegex(ValueError, 'Incomplete 600-frame'):
            measure(self.path, self.case, allow_fixture=True)

    def test_wrong_district_rejected(self):
        self.rows[100]['area_classification'] = 'other_area'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Business-district'):
            measure(self.path, self.case, allow_fixture=True)

    def test_fixture_requires_explicit_permission(self):
        self.write()
        with self.assertRaisesRegex(ValueError, 'Original Native source provenance missing'):
            measure(self.path, self.case)

    def test_position_jump_rejected(self):
        self.rows[100]['ego_center_xy_m'] = [300.0, 0.0]
        self.write()
        with self.assertRaisesRegex(ValueError, 'Implausible Native position jump'):
            measure(self.path, self.case, allow_fixture=True)

    def test_saved_original_frame_joins_and_missing_source(self):
        self.write()
        root = self.path.parent
        mapping = [{'video_frame': i, 'native_frame': i, 'time_s': i / 20}
                   for i in range(600)]
        bodies = [{'frame': i, 'time_s': i / 20,
                   'body_vertices_m': [[i * .5 - 1, -1, 0], [i * .5 + 1, -1, 0],
                                       [i * .5 + 1, 1, 0], [i * .5 - 1, 1, 0]]}
                  for i in range(600)]
        for name, values in [('video_frames.jsonl', mapping), ('body_history.jsonl', bodies)]:
            (root / name).write_text(''.join(json.dumps(value) + '\n' for value in values))
        (root / 'road_geometry.json').write_text(json.dumps({
            'area_classification': 'business_district',
            'area_classification_review_required': True,
            'native_map_sha256': 'a' * 64, 'provenance': 'synthetic_cpu_fixture'}) + '\n')
        (root / 'control_context.json').write_text(json.dumps({
            'control': 'speed_limit_sign', 'native_blueprint': 'traffic.speed_limit.30',
            'native_actor_id': 23}) + '\n')
        config = {'case_id': self.case, 'signal_distance_m': 40}
        result = process(root, config, allow_fixture=True)
        self.assertEqual(result['measured_signal_distance_m'], 40)
        self.assertEqual(len(result['source_hashes']), 5)
        self.assertFalse(result['physical_completion_claimed'])
        mapping[100]['native_frame'] = 200
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps(v) + '\n' for v in mapping))
        with self.assertRaisesRegex(ValueError, 'frame join differs'):
            process(root, config, allow_fixture=True)
        (root / 'body_history.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: body_history.jsonl'):
            process(root, config, allow_fixture=True)


if __name__ == '__main__':
    unittest.main()
