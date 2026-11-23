import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for name in ('property_route', 'route_controller'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
controller = sys.modules['route_controller']


def packet(points):
    return {'source': {'kind': 'original_native_map_and_property_authority', 'sha256': 'a' * 64},
            'properties': [{'id': 'lot', 'status': 'private', 'authority': 'original parcel authority', 'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
            'connector_routes': {'lot': points}}


class RouteControllerTests(unittest.TestCase):
    def test_bidirectional_connector_routes(self):
        east = [[-3, 5], [5, 5], [13, 5]]
        west = list(reversed(east))
        self.assertEqual(controller.validate_route(packet(east), 'lot'), [tuple(v) for v in east])
        self.assertEqual(controller.validate_route(packet(west), 'lot'), [tuple(v) for v in west])

    def test_route_missing_property_rejects(self):
        with self.assertRaisesRegex(ValueError, 'does not traverse'):
            controller.validate_route(packet([[-3, -2], [5, -2], [13, -2]]), 'lot')

    def test_missing_authority_rejects(self):
        p = packet([[-3, 5], [5, 5], [13, 5]])
        del p['properties'][0]['authority']
        with self.assertRaisesRegex(ValueError, 'classified property'):
            controller.validate_route(p, 'lot')

    def test_heading_commands_both_approach_directions(self):
        east = controller.steering_command((-3, 5), 0.0, (5, 5), 1)
        west = controller.steering_command((13, 5), 3.141592653589793, (5, 5), 1)
        self.assertAlmostEqual(east['steer'], 0.0)
        self.assertAlmostEqual(west['steer'], 0.0)
        self.assertGreater(east['throttle'], 0)

    def test_overspeed_brakes_and_turn_bounded(self):
        command = controller.steering_command((0, 0), 0, (0, 2), 7)
        self.assertEqual(command['steer'], 1.0)
        self.assertGreater(command['brake'], 0)
        self.assertEqual(command['throttle'], 0.0)


if __name__ == '__main__':
    unittest.main()
