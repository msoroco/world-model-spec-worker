import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_control import RouteControl


class RouteControlTest(unittest.TestCase):
    def test_advances_to_crossing_and_brakes_at_end(self):
        control = RouteControl([[-5, 0], [0, 0], [5, 0]])
        first = control.decide(-5, 0, 0, 0)
        self.assertEqual(first['target_index'], 1)
        self.assertGreater(first['throttle'], 0)
        middle = control.decide(0, 0, 0, 2)
        self.assertEqual(middle['target_index'], 2)
        last = control.decide(5, 0, 0, 0)
        self.assertTrue(last['requested_route_complete'])
        self.assertEqual(last['brake'], 1)

    def test_rejects_missing_route(self):
        with self.assertRaisesRegex(ValueError, 'positive route'):
            RouteControl([[0, 0]])


if __name__ == '__main__':
    unittest.main()
