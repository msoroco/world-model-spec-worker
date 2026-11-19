import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_readback import bind
from test_scene_plan import survey


class Map:
    name = 'surveyed-map'

    def get_waypoint(self, location, **kwargs):
        return types.SimpleNamespace(road_id=8, lane_id=1, lane_type='Driving')


class Actors:
    def find(self, ident):
        if ident != 12:
            return None
        return types.SimpleNamespace(id=12, type_id='walker.pedestrian.0001',
            get_transform=lambda: types.SimpleNamespace(
                location=types.SimpleNamespace(x=2, y=0, z=0)))


class World:
    def __init__(self, mapping=None):
        self.mapping = mapping or Map()

    def get_map(self):
        return self.mapping

    def get_actors(self):
        return Actors()


CARLA = types.SimpleNamespace(Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
                              LaneType=types.SimpleNamespace(Any='Any', Driving='Driving',
                                                             Shoulder='Shoulder'))


class LiveReadbackTest(unittest.TestCase):
    def test_binds_both_routes_to_original_map_and_person(self):
        x = survey(); x['anchor_z_m'] = 0.0
        receipt = bind(x, World(), CARLA)
        self.assertEqual(receipt['pavement_road_id'], 8)
        self.assertEqual(len(receipt['route_waypoints']['contrast']), 5)
        self.assertFalse(receipt['warning_act_observed'])

    def test_rejects_wrong_pavement_road(self):
        x = survey(); x['anchor_z_m'] = 0.0
        x['road_id'] = 9
        with self.assertRaisesRegex(ValueError, 'road differs'):
            bind(x, World(), CARLA)


if __name__ == '__main__':
    unittest.main()
