import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direction_comparison_audit import audit
from test_right_half_measurement import row


ASSIGNMENT = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver'


def write_case(root, suffix, direction):
    root.mkdir()
    config = {'selected_case_id': f'{ASSIGNMENT}__baseline_right_{suffix}',
              'law_id': 'NRS-484B-200-1', 'cell_id': 'C125714',
              'actor': 'motor_vehicle_driver', 'travel_direction': suffix,
              'rate_hz': 20, 'duration_s': .1, 'cameras': ['overview', 'approach',
              'reference_corner', 'driver_reference'], 'required_atoms': [],
              'source_packets': []}
    (root / 'config.json').write_text(json.dumps(config))
    rows = [row(i, direction, [.2, .2, 1.8, 1.8]) for i in range(2)]
    for name, content in {
        'video_frames.jsonl': [{'video_frame': i, 'carla_frame': i,
                                'time_s': i*.05} for i in range(2)],
        'trace.jsonl': [{'frame': i, 'time_s': i*.05} for i in range(2)],
        'directed_roadway_footprints.jsonl': rows,
    }.items():
        (root / name).write_text(''.join(json.dumps(item)+'\n' for item in content))


class DirectionComparisonAuditTests(unittest.TestCase):
    def pair(self, root):
        east, west = root / 'east', root / 'west'
        write_case(east, 'east', 1)
        write_case(west, 'west', -1)
        return east, west

    def test_positive_source_bound_direction_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            report = audit(east, west)
            self.assertEqual(report['observed_directions'], ['east', 'west'])
            self.assertTrue(report['both_bodies_entirely_right'])
            self.assertEqual(len(report['source_bindings'][0]['source_sha256']), 3)
            self.assertFalse(report['physical_acceptance_claimed'])

    def test_missing_source_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            (west / 'directed_roadway_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original'):
                audit(east, west)
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            path = west / 'trace.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]['frame'] = 99
            path.write_text(''.join(json.dumps(item)+'\n' for item in rows))
            with self.assertRaisesRegex(ValueError, 'frame join'):
                audit(east, west)

    def test_wrong_way_left_body_and_changed_camera_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            path = west / 'directed_roadway_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['travel_tangent_xy'] = [1, 0]
            path.write_text(''.join(json.dumps(item)+'\n' for item in rows))
            with self.assertRaisesRegex(ValueError, 'observed route direction'):
                audit(east, west)
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            path = west / 'directed_roadway_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['ego_corners'][0] = [0, 1]
            path.write_text(''.join(json.dumps(item)+'\n' for item in rows))
            with self.assertRaisesRegex(ValueError, 'body leaves right half'):
                audit(east, west)
        with tempfile.TemporaryDirectory() as directory:
            east, west = self.pair(Path(directory))
            path = west / 'config.json'
            config = json.loads(path.read_text())
            config['cameras'].pop()
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'fixed construction'):
                audit(east, west)


if __name__ == '__main__':
    unittest.main()
