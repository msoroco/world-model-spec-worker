"""Exercise mail action construction and retained-source rejection paths."""
import copy
import unittest

import mail_activity
from measure_exceptions import measure
from prove_measure_exceptions import context, frames


class Actor:
    def __init__(self):
        self.controls = []
        self.destroyed = False

    def apply_control(self, value):
        self.controls.append(value)

    def destroy(self):
        self.destroyed = True


class Carla:
    class Location:
        def __init__(self, **values):
            self.values = values

    class Rotation:
        def __init__(self, **values):
            self.values = values

    class Transform:
        def __init__(self, location, rotation):
            self.location, self.rotation = location, rotation

    class Vector3D:
        def __init__(self, *values):
            self.values = values

    class WalkerControl:
        def __init__(self, **values):
            self.values = values


class Library:
    def filter(self, pattern):
        return {'walker.pedestrian.*': ['walker.pedestrian.0001'],
                'static.prop.box*': ['static.prop.box01']}[pattern]


class World:
    def __init__(self):
        self.spawns = []

    def try_spawn_actor(self, blueprint, transform, attach_to=None):
        actor = Actor()
        self.spawns.append((blueprint, transform, attach_to, actor))
        return actor


def rows():
    workers, parcels, egos = [], [], []
    for frame in range(361):
        since_stop = frame - 120
        if since_stop < 20:
            y = -10.0
        elif since_stop < 70:
            y = -10.0 + (since_stop-20)*.05
        elif since_stop < 130:
            y = -7.5
        elif since_stop < 180:
            y = -7.5 - (since_stop-130)*.05
        else:
            y = -10.0
        common = {'frame': frame, 'source_kind': 'synthetic_native_sample'}
        workers.append({**common, 'blueprint': 'walker.pedestrian.0001',
                        'center_native_xy_m': [40, y]})
        parcels.append({**common, 'present': frame < 220,
                        'blueprint': 'static.prop.box01' if frame < 220 else None,
                        'center_native_xy_m': [40, y] if frame < 220 else None})
        egos.append({**common, 'time_s': frame/20,
                     'ego_center_native_xy_m': [40, -6.8]})
    return workers, parcels, egos


class MailActivityProof(unittest.TestCase):
    def test_spawn_controller_and_source_event(self):
        world = World()
        walker, parcel = mail_activity.spawn(world, Library(), Carla)
        self.assertIs(world.spawns[1][2], walker)
        self.assertEqual(world.spawns[0][1].location.values['y'], -10.0)
        phases = []
        for frame in (0, 140, 190, 220, 260, 320):
            request = mail_activity.control(walker, parcel, Carla, frame, 120)
            phases.append(request['requested_phase'])
            self.assertFalse(request['observed_native_mail_deposit'])
        self.assertEqual(phases, ['idle','approach','dwell','deposit','depart','idle'])
        self.assertTrue(parcel.destroyed)
        worker_rows, parcel_rows, ego_rows = rows()
        event = mail_activity.derive(worker_rows, parcel_rows, ego_rows, 120)[0]
        self.assertEqual(event['name'], 'mail_deposit')
        self.assertIn('unverified', event['source'])
        stop_rows = list(frames(361))
        for row in stop_rows[:120]:
            row['ego_body_native_xy_m'] = [[4,-7],[6,-7],[6,-6],[4,-6]]
        observed = measure(stop_rows, context('ordinary', sign=False, mailbox=True), [event])
        self.assertEqual(observed['recorded_activity_events'][0]['name'], 'mail_deposit')
        self.assertIsNone(observed['expeditious_mail_deposit_established'])
        self.assertIsNone(observed['legal_verdict'])

    def test_source_negative_paths(self):
        workers, parcels, egos = rows()
        altered = copy.deepcopy(parcels)
        for row in altered:
            row['present'] = True
            row['blueprint'] = 'static.prop.box01'
            row['center_native_xy_m'] = [40,-7.5]
        with self.assertRaisesRegex(ValueError, 'carried'):
            mail_activity.derive(workers, altered, egos, 120)
        altered = copy.deepcopy(parcels)
        altered[300]['present'] = True
        altered[300]['blueprint'] = 'static.prop.box01'
        altered[300]['center_native_xy_m'] = [40,-10]
        with self.assertRaisesRegex(ValueError, 'single retained parcel disappearance'):
            mail_activity.derive(workers, altered, egos, 120)
        altered = copy.deepcopy(parcels)
        altered[219]['center_native_xy_m'] = [60,-7.5]
        with self.assertRaisesRegex(ValueError, 'carried'):
            mail_activity.derive(workers, altered, egos, 120)
        altered = copy.deepcopy(workers)
        altered[220]['center_native_xy_m'] = [40,-10]
        with self.assertRaisesRegex(ValueError, 'proximity'):
            mail_activity.derive(altered, parcels, egos, 120)
        altered = copy.deepcopy(workers)
        for row in altered[240:]:
            row['center_native_xy_m'] = [40,-7.5]
        with self.assertRaisesRegex(ValueError, 'departure'):
            mail_activity.derive(altered, parcels, egos, 120)
        altered = copy.deepcopy(egos)
        altered[180]['time_s'] += 1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            mail_activity.derive(workers, parcels, altered, 120)
        altered = copy.deepcopy(parcels)
        altered[200]['source_kind'] = 'original_native'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            mail_activity.derive(workers, altered, egos, 120)


if __name__ == '__main__':
    unittest.main()
