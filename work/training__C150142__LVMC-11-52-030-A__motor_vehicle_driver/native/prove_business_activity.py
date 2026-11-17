"""CPU construction and retained-source probes for text-6 business activity."""
import copy
import unittest

import business_activity
from measure_exceptions import measure


class FakeActor:
    def __init__(self):
        self.controls = []

    def apply_control(self, value):
        self.controls.append(value)


class FakeCarla:
    class Location:
        def __init__(self, **kwargs):
            self.values = kwargs

    class Rotation:
        def __init__(self, **kwargs):
            self.values = kwargs

    class Transform:
        def __init__(self, location, rotation):
            self.location, self.rotation = location, rotation

    class Vector3D:
        def __init__(self, *values):
            self.values = values

    class WalkerControl:
        def __init__(self, **kwargs):
            self.values = kwargs


class FakeLibrary:
    def filter(self, pattern):
        assert pattern == 'walker.pedestrian.*'
        return ['walker.pedestrian.0001']


class FakeWorld:
    def __init__(self):
        self.spawned = []

    def try_spawn_actor(self, blueprint, transform):
        self.spawned.append((blueprint, transform))
        return FakeActor()


def rows(visit=True):
    worker, ego = [], []
    for i in range(361):
        since_stop = i - 120
        if not visit:
            y = -10.0
        elif since_stop < 20:
            y = -10.0
        elif since_stop < 70:
            y = -10.0 + (since_stop - 20) * .05
        elif since_stop < 130:
            y = -7.5
        elif since_stop < 180:
            y = -7.5 - (since_stop - 130) * .05
        else:
            y = -10.0
        worker.append({'frame': i, 'source_kind': 'synthetic_native_sample',
                       'blueprint': 'walker.pedestrian.0001',
                       'center_native_xy_m': [40, y]})
        ego.append({'frame': i, 'time_s': i / 20,
                    'source_kind': 'synthetic_native_sample',
                    'ego_center_native_xy_m': [40, -6.8]})
    return worker, ego


class BusinessActivityProof(unittest.TestCase):
    def test_spawn_and_controller_phases(self):
        world = FakeWorld()
        actor = business_activity.spawn(world, FakeLibrary(), FakeCarla)
        self.assertEqual(world.spawned[0][0], 'walker.pedestrian.0001')
        self.assertEqual(world.spawned[0][1].location.values['y'], -10.0)
        for frame, phase in [(0, 'idle'), (140, 'approach'), (190, 'dwell'),
                             (250, 'depart'), (300, 'idle')]:
            request = business_activity.control(actor, FakeCarla, frame, 120)
            self.assertEqual(request['requested_phase'], phase)
            self.assertFalse(request['observed_native_motion'])
        self.assertEqual([c.values['speed'] for c in actor.controls],
                         [0, 1, 0, 1, 0])

    def test_source_derived_visit_and_rejections(self):
        worker, ego = rows()
        event = business_activity.derive(worker, ego, 120)[0]
        self.assertEqual(event['name'], 'business_activity')
        self.assertEqual(event['source_kind'], 'synthetic_native_sample')
        self.assertIn('necessity unverified', event['source'])
        self.assertGreater(event['end_time_s'] - event['start_time_s'], 1)
        from prove_measure_exceptions import context, frames
        stop_rows = list(frames(361))
        for row in stop_rows[:120]:
            row['ego_body_native_xy_m'] = [[4, -7], [6, -7],
                                           [6, -6], [4, -6]]
        observed = measure(stop_rows, context('armored_car', sign=False), [event])
        self.assertEqual(observed['recorded_activity_events'][0]['name'],
                         'business_activity')
        self.assertEqual(observed['red_curb_stationary_duration_s'], 12)
        self.assertIsNone(observed['necessary_business_established'])
        with self.assertRaisesRegex(ValueError, 'approach'):
            business_activity.derive(*rows(visit=False), 120)
        altered = copy.deepcopy(worker)
        altered[200]['source_kind'] = 'original_native'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            business_activity.derive(altered, ego, 120)
        altered = copy.deepcopy(worker)
        altered[200]['frame'] = 201
        with self.assertRaisesRegex(ValueError, 'frame join'):
            business_activity.derive(altered, ego, 120)
        altered_ego = copy.deepcopy(ego)
        altered_ego[200]['time_s'] += 1
        with self.assertRaisesRegex(ValueError, 'Incomplete 20 Hz'):
            business_activity.derive(worker, altered_ego, 120)
        altered = copy.deepcopy(worker)
        for i in range(210, 240):
            altered[i]['center_native_xy_m'][1] = -10.0
        with self.assertRaisesRegex(ValueError, 'dwell'):
            business_activity.derive(altered, ego, 120)
        altered = copy.deepcopy(worker)
        for i in range(250, 361):
            altered[i]['center_native_xy_m'][1] = -7.5
        with self.assertRaisesRegex(ValueError, 'departure'):
            business_activity.derive(altered, ego, 120)


if __name__ == '__main__':
    unittest.main()
