import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('opposing_turn_measurement', ROOT / 'opposing_turn_measurement.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OpposingTurnMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.topology = self.root / 'topology.json'
        self.devices = self.root / 'devices.json'
        self.a = self.root / 'a.jsonl'
        self.b = self.root / 'b.jsonl'
        self.topology.write_text(json.dumps({'both_highways_two_directional': True,
                                             'same_intersection': True,
                                             'opposing_approaches': True}))
        self.devices.write_text(json.dumps({'governing_device': 'none'}))
        self.write_tracks()

    def write_tracks(self, *, offset=0, missing=False, opposite_turn=False):
        a, b = [], []
        def corners(x, y):
            return [[x-.25, y-.25], [x+.25, y-.25],
                    [x+.25, y+.25], [x-.25, y+.25]]
        for i in range(4):
            a.append({'frame': i, 'time_s': i*.05, 'center_xy': [i, 0],
                      'ground_corners_xy': corners(i, 0),
                      'heading_xy': [1, 0], 'in_intersection': True,
                      'turning_left': True})
            b.append({'frame': i, 'time_s': i*.05, 'center_xy': [3-i, 1+offset],
                      'ground_corners_xy': corners(3-i, 1+offset),
                      'heading_xy': [-1, 0], 'in_intersection': True,
                      'turning_left': not opposite_turn})
        if missing:
            b.pop()
        self.a.write_text(''.join(json.dumps(x)+'\n' for x in a))
        self.b.write_text(''.join(json.dumps(x)+'\n' for x in b))

    def run_measure(self):
        return module.measure(self.a, self.b, self.topology, self.devices)

    def test_original_geometry_and_distinct_crossing_clearance(self):
        close = self.run_measure()
        self.assertEqual(close['simultaneous_frames'], 4)
        self.assertEqual(close['legal_front_of_each_other'], 'unreviewed')
        self.assertEqual(close['governing_device'], 'none')
        self.assertEqual(close['source_refs'][0]['sha256'],
                         hashlib.sha256(self.a.read_bytes()).hexdigest())
        self.write_tracks(offset=2)
        far = self.run_measure()
        self.assertGreater(far['closest']['center_distance_m'],
                           close['closest']['center_distance_m'])
        self.assertGreater(far['closest']['ground_body_clearance_m'],
                           close['closest']['ground_body_clearance_m'])
        self.assertEqual(close['observations'][0]['opposing_ahead_of_subject_m'], 3)
        self.assertEqual(close['observations'][0]['subject_ahead_of_opposing_m'], 3)

    def test_missing_original_frame_rejected(self):
        self.write_tracks(missing=True)
        with self.assertRaisesRegex(ValueError, 'frame sets differ'):
            self.run_measure()

    def test_missing_body_corners_rejected(self):
        rows = [json.loads(line) for line in self.b.read_text().splitlines()]
        rows[1].pop('ground_corners_xy')
        self.b.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'ground-body corners'):
            self.run_measure()

    def test_surface_clearance_geometry(self):
        self.assertEqual(module._body_clearance([[0,0],[2,0],[2,2],[0,2]],
                                                 [[.5,.5],[1,.5],[1,1],[.5,1]]), 0)
        self.assertEqual(module._body_clearance([[0,0],[1,0],[1,1],[0,1]],
                                                 [[3,0],[4,0],[4,1],[3,1]]), 2)

    def test_no_simultaneous_left_turn_rejected(self):
        self.write_tracks(opposite_turn=True)
        with self.assertRaisesRegex(ValueError, 'no sustained simultaneous'):
            self.run_measure()

    def test_invalid_map_and_device_inventory_rejected(self):
        self.topology.write_text(json.dumps({'both_highways_two_directional': False,
                                             'same_intersection': True,
                                             'opposing_approaches': True}))
        with self.assertRaisesRegex(ValueError, 'two-directional'):
            self.run_measure()
        self.topology.write_text(json.dumps({'both_highways_two_directional': True,
                                             'same_intersection': True,
                                             'opposing_approaches': True}))
        self.devices.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'governing-device'):
            self.run_measure()


if __name__ == '__main__':
    unittest.main()
