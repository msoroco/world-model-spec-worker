import copy
import json
import unittest
from pathlib import Path

from runner import check, _source, _route_guidance, _identity, _body_footprint, _reviewed_context
from stop_controller import FRAMES, command


class DraftNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_window_and_cameras(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertEqual(receipt['source_views'],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertFalse(receipt['carla_contacted'])
        self.assertFalse(receipt['physical_completion'])
        self.assertEqual(FRAMES, 600)
        self.assertEqual(_identity(self.config['case_id']),
                         (self.config['activity_mode'],
                          self.config['case']['comparison_condition']))
        self.assertEqual(command(0, 10, 1)['phase'], 'approach')
        self.assertEqual(command(100, 0, 0)['phase'], 'hold')

    def test_no_missing_camera_or_short_window(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['frames'] = 599
        with self.assertRaisesRegex(ValueError, '600-frame'):
            check(bad)

    def test_no_wrong_identity_or_outcome(self):
        for key, value in [('actor', 'motor_vehicle_driver'),
                           ('legal_verdict', 'compliant'),
                           ('physical_completion', True),
                           ('device_source_required', False)]:
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)
        bad = copy.deepcopy(self.config)
        bad['activity_mode'] = 'park' if bad['activity_mode'] != 'park' else 'stop'
        with self.assertRaises(ValueError):
            check(bad)

    def test_sourced_route_guidance_uses_observed_pose(self):
        remaining, steer = _route_guidance((0, 0), (1, 0),
                                           [[0, 0, 0], [10, 0, 0]], (18, 0))
        self.assertAlmostEqual(remaining, 18)
        self.assertAlmostEqual(steer, 0)
        remaining, steer = _route_guidance((0, 0), (1, 0),
                                           [[0, 0, 0], [10, 2, 0]], (18, 2))
        self.assertGreater(steer, 0)
        self.assertGreater(remaining, 18)
        with self.assertRaisesRegex(ValueError, 'overshot'):
            _route_guidance((23, 0), (1, 0), [[0, 0, 0], [10, 0, 0]], (18, 0))

    def test_original_body_hull(self):
        class Vertex:
            def __init__(self, x, y):
                self.x, self.y = x, y
        vertices = [Vertex(x, y) for x, y in
                    ((0, 0), (2, 0), (2, 1), (0, 1), (1, 0), (1, 1))]
        self.assertEqual(_body_footprint(vertices),
                         [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, 'degenerate'):
            _body_footprint([Vertex(0, 0), Vertex(1, 0)])

    def test_original_device_source_gate(self):
        path = Path('missing-device-source.json')
        with self.assertRaises(FileNotFoundError):
            _source(path, 'condition_a')
        path.write_text('{}\n')
        try:
            with self.assertRaisesRegex(ValueError, 'Original official'):
                _source(path, 'condition_a')
        finally:
            path.unlink()

    def test_reviewed_context_source_gate(self):
        path = Path('context-source-test.json')
        with self.assertRaisesRegex(ValueError, 'source path required'):
            _reviewed_context(None, ('person_id',), 'Person activity')
        path.write_text('{}\n')
        try:
            with self.assertRaisesRegex(ValueError, 'review fields missing'):
                _reviewed_context(path, ('person_id',), 'Person activity')
            path.write_text('{"person_id":"operator"}\n')
            self.assertEqual(_reviewed_context(path, ('person_id',),
                                               'Person activity')['person_id'], 'operator')
        finally:
            path.unlink()
