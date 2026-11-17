"""Request a mail-drop action and derive its observable source proxy.

An observed parcel disappearance near the authored drop location is a diagnostic
activity event. It is not proof of actual U.S. mail deposit or expeditiousness.
"""
from math import hypot, isfinite

START_Y = -10.0
DROP_X = 40.0
DROP_Y = -7.4
APPROACH_START = 20
DWELL_START = 70
DEPOSIT_FRAME = 100
DWELL_END = 130
DEPART_END = 180


def spawn(world, library, carla):
    walkers = library.filter('walker.pedestrian.*')
    props = library.filter('static.prop.box*')
    if not walkers or not props:
        raise RuntimeError('Native mail actor or parcel prop unavailable')
    walker = world.try_spawn_actor(walkers[0], carla.Transform(
        carla.Location(x=DROP_X, y=START_Y, z=1), carla.Rotation(yaw=90)))
    if walker is None:
        raise RuntimeError('Native mail actor spawn failed')
    try:
        parcel = world.try_spawn_actor(props[0], carla.Transform(
            carla.Location(x=0, y=0, z=1), carla.Rotation()), attach_to=walker)
        if parcel is None:
            raise RuntimeError('Native mail parcel spawn failed')
    except Exception:
        walker.destroy()
        raise
    return walker, parcel


def control(walker, parcel, carla, frame, stationary_first_frame):
    if type(frame) is not int or frame < 0 or \
            type(stationary_first_frame) is not int or stationary_first_frame < 0:
        raise ValueError('Invalid mail-activity frame')
    since_stop = frame - stationary_first_frame
    moving = APPROACH_START <= since_stop < DWELL_START or \
        DWELL_END <= since_stop < DEPART_END
    direction = -1 if DWELL_END <= since_stop < DEPART_END else 1
    walker.apply_control(carla.WalkerControl(
        direction=carla.Vector3D(0, direction, 0),
        speed=1.0 if moving else 0.0, jump=False))
    if since_stop == DEPOSIT_FRAME:
        parcel.destroy()
    return {'frame': frame, 'source_kind': 'controller_request',
            'requested_phase': 'deposit' if since_stop == DEPOSIT_FRAME else
                'approach' if moving and direction == 1 else
                'depart' if moving else 'dwell' if DWELL_START <= since_stop < DWELL_END else 'idle',
            'observed_native_mail_deposit': False}


def point(row, key):
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 2 or any(
            type(v) not in (int, float) or not isfinite(v) for v in value):
        raise ValueError('Missing Native point: ' + key)
    return value


def derive(worker_rows, parcel_rows, ego_rows, stationary_first_frame,
           drop_x=DROP_X, drop_y=DROP_Y):
    """Require joined 20 Hz rows, approach, parcel loss, dwell and departure."""
    if type(stationary_first_frame) is not int or stationary_first_frame < 0 or \
            not (len(worker_rows) == len(parcel_rows) == len(ego_rows)) or \
            len(ego_rows) < stationary_first_frame + DEPART_END:
        raise ValueError('Missing synchronized mail source rows')
    kind = ego_rows[0].get('source_kind')
    if kind not in ('native', 'original_native', 'synthetic_native_sample'):
        raise ValueError('Invalid mail source provenance')
    if any(type(v) not in (int, float) or not isfinite(v) for v in (drop_x, drop_y)):
        raise ValueError('Invalid mail drop location')
    distances, present, times = [], [], []
    prior_time = None
    for frame, (worker, parcel, ego) in enumerate(zip(worker_rows, parcel_rows, ego_rows)):
        if any(row.get('frame') != frame or row.get('source_kind') != kind
               for row in (worker, parcel, ego)) or \
                not str(worker.get('blueprint', '')).startswith('walker.pedestrian.'):
            raise ValueError('Changed mail source frame or provenance')
        time = ego.get('time_s')
        if type(time) not in (int, float) or not isfinite(time) or \
                (prior_time is not None and not (0 < time-prior_time <= .051)):
            raise ValueError('Incomplete 20 Hz mail source interval')
        prior_time = time
        xy = point(worker, 'center_native_xy_m')
        point(ego, 'ego_center_native_xy_m')
        if type(parcel.get('present')) is not bool:
            raise ValueError('Missing Native parcel inventory')
        if parcel['present']:
            if not str(parcel.get('blueprint', '')).startswith('static.prop.'):
                raise ValueError('Changed Native parcel blueprint')
            parcel_xy = point(parcel, 'center_native_xy_m')
            if hypot(parcel_xy[0]-xy[0], parcel_xy[1]-xy[1]) > 1.5:
                raise ValueError('Parcel not carried by mail actor')
        distances.append(hypot(xy[0]-drop_x, xy[1]-drop_y))
        present.append(parcel['present'])
        times.append(time)
    if distances[stationary_first_frame] <= 2 or \
            min(distances[stationary_first_frame+1:]) > .8:
        raise ValueError('No measured mail actor approach')
    losses = [frame for frame in range(stationary_first_frame+1, len(present))
              if present[frame-1] and not present[frame]]
    if len(losses) != 1 or any(present[frame] for frame in range(losses[0], len(present))):
        raise ValueError('No single retained parcel disappearance')
    loss = losses[0]
    if distances[loss] > .8 or \
            any(distance > .8 for distance in distances[loss-10:loss+10]):
        raise ValueError('No measured mail drop proximity and dwell')
    if max(distances[loss+10:]) <= 2:
        raise ValueError('No measured mail actor departure')
    return [{'source_kind': kind, 'name': 'mail_deposit',
             'start_time_s': times[loss-1], 'end_time_s': times[loss],
             'source': 'native-mail-worker-actors.jsonl and native-mail-parcel-inventory.jsonl: parcel disappearance near drop location; actual U.S. mail deposit and expeditiousness unverified'}]
