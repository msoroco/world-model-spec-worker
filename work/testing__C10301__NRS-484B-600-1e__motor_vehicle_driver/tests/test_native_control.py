import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_control import observe


class NativeControlTests(unittest.TestCase):
    def test_complete_live_control_census_and_signal_group(self):
        position = SimpleNamespace(x=3.0, y=4.0, z=1.0)
        extent = SimpleNamespace(x=0.2, y=0.1, z=0.3)
        light = SimpleNamespace(
            id=9, type_id='traffic.traffic_light', is_alive=True,
            get_transform=lambda: SimpleNamespace(location=position),
            get_light_boxes=lambda: [SimpleNamespace(location=position,
                                                     extent=extent)],
            get_state=lambda: 'TrafficLightState.Red')
        world = SimpleNamespace(get_actors=lambda: [light])
        row = observe(world, 101, 0.0)
        self.assertEqual(row['control_actor_inventory']['actor_ids'], [9])
        self.assertTrue(row['control_actor_inventory']['complete'])
        self.assertEqual(row['devices'][0]['light_boxes'][0]['light_box_index'], 0)
        self.assertEqual(row['devices'][0]['state'], 'Red')
        duplicate = SimpleNamespace(get_actors=lambda: [light, light])
        with self.assertRaisesRegex(ValueError, 'identities invalid'):
            observe(duplicate, 101, 0.0)


if __name__ == '__main__':
    unittest.main()
