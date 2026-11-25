import json
import unittest
from pathlib import Path
from runner import check, target
from roundabout_direction import measure


class SelectedDirection(unittest.TestCase):
    def test_exact_static(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        sign = 1 if config['requested_direction'] == 'counterclockwise' else -1
        rows = []
        for i in range(600):
            xy, speed = target('ego', (i + 1) / 20, sign)
            rows.append({'frame': i, 'time_s': (i + 1) / 20,
                         'source_kind': 'authored_native_request',
                         'inside_roundabout': True, 'ego_xy_m': list(xy)})
            self.assertEqual(speed, 4.0)
        self.assertEqual(measure(rows, 'authored_native_request')
                         ['translational_direction'], config['requested_direction'])

    def test_missing_frame(self):
        config = json.loads(Path('config.json').read_text())
        sign = 1 if config['requested_direction'] == 'counterclockwise' else -1
        rows = [{'frame': i, 'time_s': (i + 1) / 20,
                 'source_kind': 'authored_native_request',
                 'inside_roundabout': True, 'ego_xy_m': list(target('ego', (i + 1)/20, sign)[0])}
                for i in range(599)]
        with self.assertRaisesRegex(ValueError, 'Full 600-frame source required'):
            measure(rows, 'authored_native_request')
