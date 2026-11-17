import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


path = Path(__file__).resolve().parents[1] / 'source_measurement.py'
spec = importlib.util.spec_from_file_location('c179480_source_measurement', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SourceMeasurementTest(unittest.TestCase):
    def rows(self):
        return [
            dict(frame=0, ego_speed_mps=3.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=4.0, following_gap_m=15.0),
            dict(frame=1, ego_speed_mps=0.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=2.0, following_gap_m=8.0),
            dict(frame=2, ego_speed_mps=0.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=0.0, following_gap_m=5.0),
        ]

    def test_original_frame_values_are_measured_without_legal_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'native-actors.jsonl'
            source.write_text(''.join(json.dumps(row)+'\n' for row in self.rows()))
            result = module.analyze(source)
        self.assertEqual(result['roadway_lane_overlap_frames'], [1, 2])
        self.assertEqual(result['following_speed_drop_mps'], 4.0)
        self.assertEqual(result['following_min_gap_m'], 5.0)
        self.assertEqual(result['normal_reasonable_movement_impeded'],
                         'independent_original_source_review_required')

    def test_missing_frame_or_source_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'native-actors.jsonl'
            rows = self.rows()
            rows[1]['frame'] = 3
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'frame join'):
                module.analyze(source)
            rows[1]['frame'] = 1
            del rows[1]['following_gap_m']
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source field'):
                module.analyze(source)

    def test_nonroadway_stop_does_not_claim_roadway_stop(self):
        rows = self.rows()
        for row in rows:
            row['ego_on_roadway'] = False
        result = module.measure(rows)
        self.assertTrue(result['complete_stop_observed'])
        self.assertEqual(result['roadway_stop_frames'], [])


if __name__ == '__main__':
    unittest.main()
