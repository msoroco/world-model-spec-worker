import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opposing_turn_comparison_audit import CAMERAS, audit


def _corners(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def _write(root, *, lateral=1., longitudinal=0., device='none', junction=12):
    root.mkdir()
    topology = {
        'source_map': {'name': 'synthetic connected map', 'opendrive_sha256': 'fixture'},
        'junction_id': junction, 'approach_road_id': 7,
        'approach_lane_ids': [-1, 1], 'exit_road_ids': [8, 8],
        'both_highways_two_directional': True, 'same_intersection': True,
        'opposing_approaches': True,
    }
    (root / 'topology_original.json').write_text(json.dumps(topology))
    (root / 'devices_original.json').write_text(json.dumps({'governing_device': device}))
    for name in CAMERAS:
        (root / name).write_bytes(b'synthetic camera source')
    for name, opposing in (('subject_original.jsonl', False),
                            ('opposing_original.jsonl', True)):
        rows = []
        for frame in range(4):
            x, y = ((3-frame+longitudinal, lateral) if opposing else (frame, 0.))
            rows.append({'frame': frame, 'time_s': frame / 20,
                         'center_xy': [x, y], 'heading_xy': [-1, 0] if opposing else [1, 0],
                         'ground_corners_xy': _corners(x, y),
                         'in_intersection': True, 'turning_left': True})
        (root / name).write_text(''.join(json.dumps(row)+'\n' for row in rows))


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.left = Path(self.temp.name) / 'left'
        self.right = Path(self.temp.name) / 'right'
        _write(self.left)
        _write(self.right, lateral=2., longitudinal=1.)

    def test_crossing_contrast_and_fixed_source_rejections(self):
        result = audit(self.left, self.right, 'uncontrolled_front_vs_rear')
        self.assertEqual(result['simultaneous_frames'], 4)
        self.assertEqual(result['legal_front_of_each_other'], 'unreviewed')
        self.assertEqual(len(result['sources']), 16)
        topology = json.loads((self.right / 'topology_original.json').read_text())
        topology['junction_id'] = 13
        (self.right / 'topology_original.json').write_text(json.dumps(topology))
        with self.assertRaisesRegex(ValueError, 'fixed original topology'):
            audit(self.left, self.right, 'uncontrolled_front_vs_rear')

    def test_device_contrast_requires_fixed_trajectories(self):
        (self.right / 'devices_original.json').write_text(json.dumps({'governing_device': 'directs_alternate'}))
        with self.assertRaisesRegex(ValueError, 'fixed original actor trajectories'):
            audit(self.left, self.right, 'device_direction_exception')
        _write_same_tracks = (self.left / 'opposing_original.jsonl').read_bytes()
        (self.right / 'opposing_original.jsonl').write_bytes(_write_same_tracks)
        result = audit(self.left, self.right, 'device_direction_exception')
        self.assertEqual(result['comparison_id'], 'device_direction_exception')

    def test_missing_camera_and_missing_geometry_contrast_rejected(self):
        (self.right / 'overview.mkv').unlink()
        with self.assertRaisesRegex(ValueError, 'named comparison camera'):
            audit(self.left, self.right, 'uncontrolled_front_vs_rear')
        (self.right / 'overview.mkv').write_bytes(b'synthetic camera source')
        (self.right / 'opposing_original.jsonl').write_bytes(
            (self.left / 'opposing_original.jsonl').read_bytes())
        with self.assertRaisesRegex(ValueError, 'crossing-geometry contrast'):
            audit(self.left, self.right, 'uncontrolled_front_vs_rear')


if __name__ == '__main__':
    unittest.main()
