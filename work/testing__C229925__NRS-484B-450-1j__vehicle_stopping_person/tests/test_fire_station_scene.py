import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fire_station_scene', ROOT / 'fire_station_scene.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Adapter:
    def __init__(self):
        self.calls = []
        self.actors = []

    def place_entrance(self, markers, start, end):
        self.calls.append(('entrance', len(markers), start, end))

    def spawn_vehicle(self, point, blueprint):
        actor = object()
        self.actors.append(actor)
        self.calls.append(('spawn', point, blueprint))
        return actor

    def set_halt_route(self, actor, point, activity):
        self.calls.append(('halt', point, activity))

    def set_traffic_route(self, actor, point):
        self.calls.append(('traffic', point))

    def set_context(self, circumstance, authority, person):
        self.calls.append(('context', circumstance, authority, person))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def scene(case):
    # Textual unit scene only; there is no asserted original map or fire station.
    y = -2.0 if case.side == 'opposite' else 2.0
    entrance_y = 2.0
    lateral = abs(y - entrance_y)
    distance_m = case.distance_ft * .3048
    x = (distance_m ** 2 - lateral ** 2) ** .5
    data = {
        'law_id': module.LAW, 'cell_id': 'C229925',
        'actor': 'vehicle_stopping_person', 'vehicle_class': 'vehicle',
        'stopping_person_id': 'unit-person', 'side_request': case.side,
        'activity_request': case.activity,
        'circumstance_request': case.circumstance,
        'nominal_entrance_distance_ft': case.distance_ft,
        'entrance_start_xy': [0.0, entrance_y],
        'entrance_end_xy': [1.0, entrance_y],
        'road_origin_xy': [0.0, 0.0], 'road_forward_xy': [1.0, 0.0],
        'vehicle_start_xy': [x + 12.0, y], 'vehicle_target_xy': [x + 1.0, y],
        'station_is_fire': case.circumstance != 'non_fire_station',
        'highway_public_use': case.circumstance != 'private_road',
        'highway_dedicated': True, 'vehicle_blueprint_id': 'vehicle.unit',
        'entrance_markers': [
            {'blueprint_id': 'static.unit', 'xy': [0.0, entrance_y]},
            {'blueprint_id': 'static.unit', 'xy': [1.0, entrance_y]}],
        'authority_record_id': 'unit-authority',
        'conflicting_vehicle_start_xy': [x - 10, y],
        'conflicting_vehicle_target_xy': [x + 20, y],
        'conflicting_vehicle_blueprint_id': 'vehicle.unit'}
    for key in ('station_identity', 'entrance_boundary', 'highway_boundary',
                'highway_dedication', 'public_vehicular_use', 'entrance_side',
                'stopping_person', 'halt_purpose', 'traffic_conflict',
                'law_direction', 'police_direction', 'official_device_direction'):
        data[key + '_source'] = 'unit:' + key
    return data


class SceneTests(unittest.TestCase):
    def test_all_exact_cases_construct_and_isolate_variables(self):
        for case in module.CASES:
            with self.subTest(case=case.name):
                adapter = Adapter()
                result = module.construct(adapter, scene(case), case)
                self.assertEqual(result['case_id'], case.case_id)
                self.assertEqual(len([x for x in adapter.calls if x[0] == 'spawn']),
                                 2 if case.circumstance == 'traffic_conflict' else 1)
                self.assertEqual(len([x for x in adapter.calls if x[0] == 'halt']), 1)

    def test_side_cannot_be_relabelled(self):
        case = module.CASES[0]
        data = scene(case)
        data['vehicle_target_xy'][1] = 2.0
        with self.assertRaisesRegex(ValueError, 'requested highway side'):
            module.validate_scene(data, case)

    def test_missing_source_is_rejected(self):
        case = module.CASES[0]
        data = scene(case)
        del data['station_identity_source']
        with self.assertRaisesRegex(ValueError, 'independent source missing'):
            module.validate_scene(data, case)

    def test_no_physical_conflict_actor_rejected(self):
        case = next(x for x in module.CASES if x.circumstance == 'traffic_conflict')
        data = scene(case)
        del data['conflicting_vehicle_start_xy']
        with self.assertRaisesRegex(ValueError, 'physical vehicle'):
            module.validate_scene(data, case)


if __name__ == '__main__':
    unittest.main()
