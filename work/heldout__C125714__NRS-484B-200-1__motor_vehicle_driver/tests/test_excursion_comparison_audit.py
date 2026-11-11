import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from excursion_comparison_audit import audit
from test_right_half_measurement import row


ASSIGNMENT = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver'


def write_attempt(root, suffix, crossing):
    root.mkdir()
    config = {'selected_case_id': ASSIGNMENT+'__'+suffix,
              'law_id': 'NRS-484B-200-1', 'cell_id': 'C125714',
              'actor': 'motor_vehicle_driver', 'travel_direction': 'east',
              'rate_hz': 20, 'duration_s': .1, 'cameras': ['overview', 'approach',
              'reference_corner', 'driver_reference'], 'required_atoms': [],
              'source_packets': []}
    (root/'config.json').write_text(json.dumps(config))
    geometry = [row(0, 1, [.2, .2, 1.8, 1.8]),
                row(1, 1, [-.2, -.2, 1.8, 1.8] if crossing else [.2, .2, 1.8, 1.8])]
    for item in geometry:
        item['subject_road_id'] = 1
        item['subject_lane_id'] = -1
    sources = {
        'video_frames.jsonl': [{'video_frame': i, 'carla_frame': i,
                                'time_s': i*.05} for i in range(2)],
        'trace.jsonl': [{'frame': i, 'time_s': i*.05} for i in range(2)],
        'directed_roadway_footprints.jsonl': geometry,
    }
    for name, entries in sources.items():
        (root/name).write_text(''.join(json.dumps(item)+'\n' for item in entries))


class ExcursionComparisonAuditTests(unittest.TestCase):
    def pair(self, root):
        baseline, excursion = root/'baseline', root/'excursion'
        write_attempt(baseline, 'baseline_right_east', False)
        write_attempt(excursion, 'unexcepted_left', True)
        return baseline, excursion

    def test_original_body_crossing_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            report = audit(baseline, excursion)
            self.assertEqual(report['source_bindings'][1]['first_crossing_frame'], 1)
            self.assertFalse(report['physical_acceptance_claimed'])

    def test_missing_source_stale_join_and_no_crossing_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            (excursion/'directed_roadway_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original excursion source'):
                audit(baseline, excursion)
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            path = excursion/'trace.jsonl'
            entries = [json.loads(s) for s in path.read_text().splitlines()]
            entries[1]['frame'] = 99
            path.write_text(''.join(json.dumps(x)+'\n' for x in entries))
            with self.assertRaisesRegex(ValueError, 'frame/time join'):
                audit(baseline, excursion)
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            write_attempt_override = excursion/'directed_roadway_footprints.jsonl'
            entries = [json.loads(s) for s in write_attempt_override.read_text().splitlines()]
            entries[1]['ego_corners'][0][1] = .2
            entries[1]['ego_corners'][1][1] = .2
            write_attempt_override.write_text(''.join(json.dumps(x)+'\n' for x in entries))
            with self.assertRaisesRegex(ValueError, 'never crosses centerline'):
                audit(baseline, excursion)

    def test_fixed_camera_and_route_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            path = excursion/'config.json'
            config = json.loads(path.read_text())
            config['cameras'].pop()
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'fixed construction'):
                audit(baseline, excursion)
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            path = excursion/'directed_roadway_footprints.jsonl'
            entries = [json.loads(s) for s in path.read_text().splitlines()]
            entries[1]['subject_road_id'] = 2
            path.write_text(''.join(json.dumps(x)+'\n' for x in entries))
            with self.assertRaisesRegex(ValueError, 'route identity'):
                audit(baseline, excursion)
        with tempfile.TemporaryDirectory() as directory:
            baseline, excursion = self.pair(Path(directory))
            path = excursion/'directed_roadway_footprints.jsonl'
            entries = [json.loads(s) for s in path.read_text().splitlines()]
            for item in entries:
                item['right_road_edge_xy'][1] += 1
            path.write_text(''.join(json.dumps(x)+'\n' for x in entries))
            with self.assertRaisesRegex(ValueError, 'roadway width differs'):
                audit(baseline, excursion)


if __name__ == '__main__':
    unittest.main()
