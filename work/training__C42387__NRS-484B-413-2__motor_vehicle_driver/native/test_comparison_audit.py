"""Positive and changed-fixed-source comparison mechanics on CPU fixtures."""
import json
import tempfile
import unittest
from pathlib import Path

from comparison_audit import audit
from measure_observed import CASE_PREFIX
from saved_measure import process


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


class ComparisonSourceAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = []
        self.receipts = []
        for suffix, onset, target in [('a', 230, 35), ('b', 260, 20)]:
            attempt = self.root / suffix
            attempt.mkdir()
            case = CASE_PREFIX + suffix
            samples = [{'provenance': 'synthetic_cpu_fixture', 'case_id': case,
                        'sample_index': i, 'native_frame': 200 + i, 'time_s': i / 20,
                        'ego_center_xy_m': [i * .5, 0.0],
                        'ego_heading_deg': 0 if i < 300 else 10,
                        'ego_speed_mps': 10.0, 'right_lamp_commanded': i >= onset,
                        'right_lamp_observed': i >= onset,
                        'course_change_observed': i >= 300,
                        'area_classification': 'business_district',
                        'precipitation': 'clear',
                        'other_vehicle': {'native_actor_id':23,'center_xy_m':[-45,-1.75],
                                          'heading_deg':180,'speed_mps':0,'alive':True}} for i in range(600)]
            mapping = [{'video_frame': i, 'native_frame': 200 + i,
                        'time_s': i / 20} for i in range(600)]
            bodies = [{'frame': 200 + i, 'time_s': i / 20,
                       'body_vertices_m': [[i * .5 - 1, -1, 0], [i * .5 + 1, -1, 0],
                                           [i * .5 + 1, 1, 0], [i * .5 - 1, 1, 0]]}
                      for i in range(600)]
            for name, rows in [('native_samples.jsonl', samples),
                               ('video_frames.jsonl', mapping),
                               ('body_history.jsonl', bodies)]:
                write_rows(attempt / name, rows)
            (attempt / 'road_geometry.json').write_text(json.dumps({
                'area_classification': 'business_district',
                'area_classification_review_required': True,
                'native_map_sha256': 'a' * 64,
                'provenance': 'synthetic_cpu_fixture'}) + '\n')
            (attempt / 'control_context.json').write_text(json.dumps({
                'control': 'other_vehicle',
                'native_blueprint': 'vehicle.lincoln.mkz_2020',
                'native_actor_id': 23, 'native_road_id':1,'native_lane_id':1,
                'stationary_opposing_lane_plan':True}) + '\n')
            config = {'case_id': case, 'law_id': 'NRS-484B-413-2',
                      'cell_id': 'C42387', 'actor': 'motor_vehicle_driver',
                      'layout': 'business_district', 'maneuver': 'right_turn',
                      'precipitation': 'clear', 'rate_hz': 20, 'duration_s': 30,
                      'signal_distance_m': target,
                      'cameras': [{'name': name, 'width': width, 'height': height, 'fps': 20}
                                  for name, width, height in
                          (('overview', 1920, 1080), ('approach', 1280, 720),
                           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]}
            (attempt / 'config.json').write_text(json.dumps(config) + '\n')
            receipt = self.root / (suffix + '-receipt.json')
            receipt.write_text(json.dumps(process(attempt, config,
                                                  allow_fixture=True)) + '\n')
            self.paths.append(attempt)
            self.receipts.append(receipt)

    def run_audit(self):
        return audit(*self.paths, *self.receipts, allow_fixture=True)

    def test_comparison_and_missing_source(self):
        result = self.run_audit()
        self.assertEqual(result['measured_distances_m'], [35.0, 20.0])
        self.assertFalse(result['physical_acceptance_claimed'])
        (self.paths[1] / 'body_history.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or stale original comparison source'):
            self.run_audit()

    def test_changed_fixed_condition_rejected(self):
        path = self.paths[1] / 'config.json'
        config = json.loads(path.read_text())
        config['precipitation'] = 'rain'
        path.write_text(json.dumps(config) + '\n')
        with self.assertRaisesRegex(ValueError, 'Comparison fixed conditions changed'):
            self.run_audit()

    def test_changed_saved_measurement_rejected(self):
        path = self.receipts[0]
        receipt = json.loads(path.read_text())
        receipt['measured_signal_distance_m'] = 99
        path.write_text(json.dumps(receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'Saved signal measurement differs'):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
