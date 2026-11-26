"""CPU checks of the reviewed-route Native spawn and motion adapter."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_original import Adapter


class NativeAdapterTests(unittest.TestCase):
    def adapter(self, variant, first=0.0):
        calls = []
        site = {'road': {'exit_waypoints': [[first, 0, 0], [first + 2, 0, 0],
                                             [first + 8, 0, 0]]}}
        actor = SimpleNamespace(id=3, get_location=lambda: SimpleNamespace(x=first + 2, y=0),
                                set_target_velocity=lambda velocity: calls.append(velocity))
        world = SimpleNamespace(
            get_map=lambda: SimpleNamespace(get_waypoint=lambda location, project_to_road:
                                            SimpleNamespace(transform=SimpleNamespace(rotation=None))),
            get_blueprint_library=lambda: SimpleNamespace(find=lambda blueprint: blueprint),
            try_spawn_actor=lambda blueprint, transform: (calls.append(transform.location), actor)[1])
        carla = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values),
                                Transform=lambda location, rotation: SimpleNamespace(location=location),
                                Vector3D=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z))
        return Adapter(world, carla, site, variant), calls

    def test_primary_and_fallback_use_distinct_reviewed_waypoints(self):
        primary, primary_calls = self.adapter('primary')
        fallback, fallback_calls = self.adapter('fallback1')
        primary.spawn_vehicle([0, 0, 0], 'vehicle.car', 'ego')
        fallback.spawn_vehicle([0, 0, 0], 'vehicle.car', 'ego')
        self.assertEqual(primary_calls[0].x - fallback_calls[0].x, 2.0)

    def test_unreviewed_fallback_spacing_rejected(self):
        adapter, _ = self.adapter('fallback1', first=1.0)
        adapter.site['road']['exit_waypoints'][1][0] = 4.0
        with self.assertRaisesRegex(ValueError, 'two-meter'):
            adapter.spawn_vehicle([1, 0, 0], 'vehicle.car', 'ego')


if __name__ == '__main__':
    unittest.main()
