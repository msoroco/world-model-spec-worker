"""CPU checks for physical construction and original source rejection."""
import unittest

from flashing_red_native import CASES, build_case, measure_original, reference


def site(kind='crosswalk'):
    refs = {'crosswalk': 20.0 if kind == 'crosswalk' else None,
            'limit_line': 21.0 if kind == 'limit_line' else None,
            'intersection': 25.0}
    result = {'assignment_id': 'testing__C24751__NRS-484B-310-1__heavy_vehicle_driver',
              'cell_id': 'C24751', 'layout': 'blind_intersection',
              'control': 'flashing_red_signal', 'official_device': True,
              'approach_id': 'eastbound', 'signal_approach_id': 'eastbound',
              'signal_support': 'spawned_prop', 'occluder_support': 'spawned_prop',
              'approach_waypoints': [[0.0, 0.0], [30.0, 0.0]],
              'lane_width_m': 3.8, 'ego_width_m': 2.5, 'ego_length_m': 10.0,
              'occluder_corners_m': [[10.0, 4.0], [12.0, 4.0],
                                     [12.0, 6.0], [10.0, 6.0]],
              'stop_references_m': refs, 'signal_geometry': {'x_m': 23.0}}
    for name in ('map', 'approach_source', 'signal_identity', 'signal_geometry',
                 'signal_blueprint', 'occluder_identity', 'occluder_geometry',
                 'occluder_blueprint', 'ego_blueprint', 'camera_plan', 'stop_geometry'):
        result[name + '_sha256'] = 'source-' + name
    return result


class FakeAdapter:
    def __init__(self):
        self.created = []
        self.targets = []

    def spawn_signal(self, *_):
        self.created.append('signal')
        return 'signal'

    def read_signal(self, *_):
        return {'identity_sha256': 'source-signal_identity',
                'geometry_sha256': 'source-signal_geometry',
                'official_device': True, 'governed_approach_id': 'eastbound'}

    def spawn_occluder(self, *_):
        self.created.append('occluder')
        return 'occluder'

    def read_occluder(self, *_):
        return {'identity_sha256': 'source-occluder_identity',
                'geometry_sha256': 'source-occluder_geometry',
                'physically_present': True}

    def spawn_heavy_vehicle(self, *_):
        self.created.append('ego')
        return 'ego'

    def read_vehicle(self, *_):
        return {'actor_class': 'heavy_vehicle', 'length_m': 10.0, 'width_m': 2.5}

    def set_route(self, *_):
        pass

    def set_flashing_red(self, *_):
        pass

    def set_controller_tuning(self, _, engineering):
        self.tuning = engineering

    def set_stop_target(self, _, target):
        self.targets.append(target)

    def destroy(self, actor):
        self.created.remove(actor)


class NativeConstructionTest(unittest.TestCase):
    def test_all_four_exact_stopping_alternatives(self):
        for case, kind in zip(CASES, ('crosswalk', 'crosswalk',
                                      'limit_line', 'intersection')):
            adapter = FakeAdapter()
            built = build_case(adapter, site(kind), case)
            self.assertEqual(built['target_front_m'], reference(site(kind), case)
                             + case.stop_offset_m)
            self.assertEqual(built['owned'], ('signal', 'occluder', 'ego'))
            self.assertEqual(len(adapter.targets), 1)

    def test_wrong_governance_rejected(self):
        packet = site()
        packet['signal_approach_id'] = 'westbound'
        with self.assertRaisesRegex(ValueError, 'governance'):
            build_case(FakeAdapter(), packet, CASES[0])

    def test_no_occluder_rejected(self):
        packet = site()
        packet['occluder_corners_m'] = []
        with self.assertRaisesRegex(ValueError, 'occluder'):
            build_case(FakeAdapter(), packet, CASES[0])

    def test_reference_alternative_rejected_when_crosswalk_present(self):
        with self.assertRaisesRegex(ValueError, 'no crosswalk'):
            reference(site('crosswalk'), CASES[2])

    def test_original_flash_and_stop(self):
        packet = site()
        fixed = {'actor_id': 1, 'signal_actor_id': 2, 'occluder_actor_id': 3,
                 'site_sha256': 'source-site', 'frame_map_sha256': 'source-map'}
        fixed.update({name: packet[name] for name in
                     ('map_sha256', 'signal_identity_sha256',
                      'occluder_identity_sha256', 'stop_geometry_sha256',
                      'camera_plan_sha256')})
        rows = [dict(fixed, case_id=packet['assignment_id'] + '__crosswalk_stop',
                     frame=100 + i, time_s=i / 20, red_lit=(i % 2 == 0),
                     front_m=18.5 + 0.1 * i, speed_mps=(0.0 if i == 3 else 1.0),
                     signal_approach_id='eastbound', official_device=True,
                     signal_physically_present=True,
                     occluder_physically_present=True) for i in range(4)]
        measurement = measure_original(rows, packet, CASES[0])
        self.assertEqual(measurement['flashing_red_transitions'], 3)
        self.assertTrue(measurement['stop_observations'][0]['before_reference'])
        rows[1]['occluder_physically_present'] = False
        with self.assertRaisesRegex(ValueError, 'physical signal or occluder'):
            measure_original(rows, packet, CASES[0])


if __name__ == '__main__':
    unittest.main()
