"""Construct and measure a service worker's visit beside a parked vehicle.

The visit is an observable activity proxy. It does not establish the statutory
purpose or that the parked interval was necessary for that business.
"""
from math import hypot, isfinite

START_Y = -10.0
VEHICLE_Y = -6.8
APPROACH_START = 20
DWELL_START = 70
DWELL_END = 130
DEPART_END = 180


def spawn(world, library, carla):
    walkers = library.filter('walker.pedestrian.*')
    if not walkers:
        raise RuntimeError('Native service-worker blueprint unavailable')
    actor = world.try_spawn_actor(walkers[0], carla.Transform(
        carla.Location(x=40, y=START_Y, z=1), carla.Rotation(yaw=90)))
    if actor is None:
        raise RuntimeError('Native service-worker spawn failed')
    return actor


def control(actor, carla, frame, stationary_first_frame):
    if type(frame) is not int or frame < 0 or \
            type(stationary_first_frame) is not int or stationary_first_frame < 0:
        raise ValueError('Invalid business-activity frame')
    since_stop = frame - stationary_first_frame
    if APPROACH_START <= since_stop < DWELL_START:
        direction, moving = 1, True
    elif DWELL_END <= since_stop < DEPART_END:
        direction, moving = -1, True
    else:
        direction, moving = 1, False
    actor.apply_control(carla.WalkerControl(
        direction=carla.Vector3D(0, direction, 0),
        speed=1.0 if moving else 0.0, jump=False))
    return {'frame': frame, 'requested_phase':
            'approach' if direction == 1 and moving else
            'depart' if moving else
            'dwell' if DWELL_START <= since_stop < DWELL_END else 'idle',
            'source_kind': 'controller_request', 'observed_native_motion': False}


def _point(row, name):
    point = row.get(name)
    if not isinstance(point, list) or len(point) != 2 or any(
            type(value) not in (int, float) or not isfinite(value)
            for value in point):
        raise ValueError('Missing Native position: ' + name)
    return point


def derive(worker_rows, ego_rows, first_stationary_frame=0):
    """Require approach, sustained proximity, departure and 20 Hz row joins."""
    if type(first_stationary_frame) is not int or first_stationary_frame < 0 or \
            len(worker_rows) != len(ego_rows) or len(worker_rows) < 6:
        raise ValueError('Missing synchronized service-worker source rows')
    kind = ego_rows[0].get('source_kind')
    if kind not in ('native', 'original_native', 'synthetic_native_sample'):
        raise ValueError('Invalid service-worker source provenance')
    distances = []
    times = []
    prior = None
    for i, (worker, ego) in enumerate(zip(worker_rows, ego_rows)):
        if worker.get('frame') != i or ego.get('frame') != i or \
                worker.get('source_kind') != kind or ego.get('source_kind') != kind or \
                not str(worker.get('blueprint', '')).startswith('walker.pedestrian.'):
            raise ValueError('Changed service-worker provenance or frame join')
        time = ego.get('time_s')
        if type(time) not in (int, float) or not isfinite(time) or \
                (prior is not None and not (0 < time - prior <= .051)):
            raise ValueError('Incomplete 20 Hz service-worker source interval')
        prior = time
        worker_xy = _point(worker, 'center_native_xy_m')
        ego_xy = _point(ego, 'ego_center_native_xy_m')
        distances.append(hypot(worker_xy[0] - ego_xy[0],
                               worker_xy[1] - ego_xy[1]))
        times.append(time)
    if first_stationary_frame >= len(distances):
        raise ValueError('No service-worker visit during stop')
    close = [i for i in range(first_stationary_frame, len(distances))
             if distances[i] <= 2.0]
    if not close or close[0] <= first_stationary_frame or \
            distances[first_stationary_frame] <= 2.5:
        raise ValueError('No measured service-worker approach')
    first, last = close[0], close[-1]
    if last - first < 20 or any(distances[i] > 2.0 for i in range(first, last + 1)):
        raise ValueError('No sustained service-worker dwell')
    if last >= len(distances) - 1 or max(distances[last + 1:]) <= 2.5:
        raise ValueError('No measured service-worker departure')
    return [{'source_kind': kind, 'name': 'business_activity',
             'start_time_s': times[first], 'end_time_s': times[last],
             'source': 'native-service-worker-actors.jsonl: approach, dwell, departure; purpose and necessity unverified'}]
