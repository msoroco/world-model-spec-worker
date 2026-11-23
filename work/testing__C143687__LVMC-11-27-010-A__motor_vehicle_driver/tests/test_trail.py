import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / 'trail.py'
spec = importlib.util.spec_from_file_location('trail_case', MODULE)
trail = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = trail
spec.loader.exec_module(trail)


def site_for(case):
    return {
        'cell_id': 'C143687', 'layout': 'nonmotorized_trail',
        'map_sha256': 'map', 'corridor_source_sha256': 'corridor',
        'corridor_box_xy': [0, 0, 20, 5],
        'route_xy': [[1, 2], [10, 2], [19, 2]],
        'administrative_records': {
            'official_plan_designation': {'asserted': case.designated, 'source_sha256': 'plan'},
            'city_trail_dedication': {'asserted': case.dedicated, 'source_sha256': 'deed'},
        },
        'sign': {'source_sha256': 'sign', 'governed_access_sha256': 'access',
                 'position_xy': [2, 2], 'face_readback_sha256': 'face',
                 'face_text': 'NO MOTOR VEHICLES' if case.prohibition_posted else 'TRAIL ACCESS',
                 'prohibits_motor_vehicles': case.prohibition_posted},
        'vehicle_blueprint': 'vehicle.test', 'vehicle_class_source_sha256': 'class',
        'operator_source_sha256': 'operator', 'exception_status_source_sha256': 'status',
        'emergency_use': case.emergency_use, 'maintenance_use': case.maintenance_use,
        'target_speed_mps': 3.0,
    }


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.destroyed = []
        self.fail = fail

    def install_sign(self, *args, **kwargs):
        self.calls.append(('sign', args, kwargs))
        return 'sign'

    def spawn_vehicle(self, *args, **kwargs):
        self.calls.append(('vehicle', args, kwargs))
        if self.fail:
            raise RuntimeError('spawn failed')
        return 'vehicle'

    def set_route(self, *args, **kwargs):
        self.calls.append(('route', args, kwargs))

    def bind_status(self, *args, **kwargs):
        self.calls.append(('status', args, kwargs))

    def destroy(self, actor):
        self.destroyed.append(actor)


class TrailTests(unittest.TestCase):
    def test_every_case_constructs_real_sign_and_route(self):
        for case in trail.CASES:
            with self.subTest(case=case.name):
                adapter = Adapter()
                result = trail.build_case(adapter, site_for(case), case)
                self.assertEqual(result['owned'], ('sign', 'vehicle'))
                self.assertEqual([x[0] for x in adapter.calls],
                                 ['sign', 'vehicle', 'route', 'status'])
                self.assertEqual(adapter.calls[-1][2]['emergency_use'], case.emergency_use)
                self.assertEqual(adapter.calls[-1][2]['maintenance_use'], case.maintenance_use)

    def test_unsigned_administrative_fact_is_rejected(self):
        case = trail.CASES[0]
        site = site_for(case)
        site['administrative_records']['city_trail_dedication']['source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'dedication affirmative source'):
            trail.build_case(Adapter(), site, case)

    def test_wrong_route_and_sign_are_rejected(self):
        case = trail.CASES[0]
        site = site_for(case)
        site['route_xy'][1] = [30, 2]
        with self.assertRaisesRegex(ValueError, 'inside corridor'):
            trail.validate_source(site, case)
        site = site_for(case)
        site['sign']['prohibits_motor_vehicles'] = False
        with self.assertRaisesRegex(ValueError, 'sign content differs'):
            trail.validate_source(site, case)

    def test_cleanup_on_failed_spawn(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'spawn failed'):
            trail.build_case(adapter, site_for(trail.CASES[0]), trail.CASES[0])
        self.assertEqual(adapter.destroyed, ['sign'])


if __name__ == '__main__':
    unittest.main()
