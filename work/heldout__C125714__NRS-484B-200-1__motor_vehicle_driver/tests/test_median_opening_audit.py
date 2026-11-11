from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from median_opening_audit import audit
from test_median_opening_route import reference


class MedianOpeningAuditTests(unittest.TestCase):
    def make_attempt(self, directory):
        directory = Path(directory)
        ref = {**reference(), 'travel_direction': 'east'}
        config = {'selected_case_id': 'exact-east', 'median_opening_reference': ref}
        receipt = {'case_id': 'exact-east', 'map_name': ref['map_name'],
                   'road_id': ref['road_id'], 'lane_id': ref['lane_id'],
                   'opening_reference_sha256': hashlib.sha256(json.dumps(
                       ref, sort_keys=True).encode()).hexdigest(),
                   'frames': [10, 11, 12], 'observed_opening_frames': [10, 11],
                   'opening_sample_indices': [2, 3],
                   'physical_median_verified': False, 'delivery_ready': False}
        rows = [{'frame': frame, 'subject_road_id': ref['road_id'],
                 'subject_lane_id': ref['lane_id'],
                 'roadway_center_point_xy': xy} for frame, xy in
                [(10, [5, 0]), (11, [7, 0]), (12, [20, 0])]]
        (directory / 'config.json').write_text(json.dumps(config))
        (directory / 'construction-probe.json').write_text(json.dumps(receipt))
        (directory / 'directed_roadway_footprints.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in rows))
        return receipt, rows

    def test_source_bound_observed_opening_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt, rows = self.make_attempt(temp)
            self.assertEqual(audit(temp)['observed_opening_frames'], [10, 11])
            receipt['observed_opening_frames'] = [10, 12]
            (Path(temp) / 'construction-probe.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'differs from original'):
                audit(temp)
            receipt['observed_opening_frames'] = [10, 11]
            receipt['delivery_ready'] = True
            (Path(temp) / 'construction-probe.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'unsupported readiness'):
                audit(temp)
            receipt['delivery_ready'] = False
            receipt['opening_sample_indices'] = [2, 4]
            (Path(temp) / 'construction-probe.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'route samples'):
                audit(temp)
            receipt['opening_sample_indices'] = [2, 3]
            (Path(temp) / 'construction-probe.json').write_text(json.dumps(receipt))
            rows[1]['roadway_center_point_xy'] = [30, 0]
            (Path(temp) / 'directed_roadway_footprints.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'differs from original'):
                audit(temp)


if __name__ == '__main__':
    unittest.main()
