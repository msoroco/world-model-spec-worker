from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from closure_source_audit import audit


def write_rows(directory, closure, roadway):
    directory = Path(directory)
    for name, rows in [('closure_devices.jsonl', closure),
                       ('directed_roadway_footprints.jsonl', roadway)]:
        (directory / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))


def source_rows():
    closure = []
    roadway = []
    for frame, time_s in [(10, 0.0), (11, .05)]:
        closure.append({'frame': frame, 'time_s': time_s,
                        'authority_verified': False,
                        'devices': [{'actor_id': str(i),
                                     'blueprint_id': 'static.prop.trafficcone01',
                                     'position_m': [10, y, .05]}
                                    for i, y in [(1, .6), (2, 2.0), (3, 3.4)]]})
        roadway.append({'frame': frame, 'time_s': time_s,
                        'roadway_center_point_xy': [10, 0],
                        'travel_tangent_xy': [1, 0],
                        'subject_lane_width_m': 4.0})
    return closure, roadway


class ClosureSourceAuditTests(unittest.TestCase):
    def test_join_right_half_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            closure, roadway = source_rows()
            write_rows(directory, closure, roadway)
            receipt = audit(directory)
            self.assertEqual(receipt['cone_actor_ids'], ['1', '2', '3'])
            self.assertFalse(receipt['authority_verified'])
            closure[1]['devices'][0]['position_m'][1] = -.5
            write_rows(directory, closure, roadway)
            with self.assertRaisesRegex(ValueError, 'moved'):
                audit(directory)
            closure, roadway = source_rows()
            closure[0]['authority_verified'] = True
            write_rows(directory, closure, roadway)
            with self.assertRaisesRegex(ValueError, 'unproved authority'):
                audit(directory)
            closure, roadway = source_rows()
            roadway[1]['frame'] = 12
            write_rows(directory, closure, roadway)
            with self.assertRaisesRegex(ValueError, 'frame/time join'):
                audit(directory)


if __name__ == '__main__':
    unittest.main()
