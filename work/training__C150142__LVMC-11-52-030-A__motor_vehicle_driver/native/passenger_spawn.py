"""Lazy CARLA passenger actor setup and 20 Hz approach control."""


def spawn(world, library, carla):
    walkers = library.filter('walker.pedestrian.*')
    if not walkers:
        raise RuntimeError('Native passenger blueprint unavailable')
    actor = world.try_spawn_actor(walkers[0], carla.Transform(
        carla.Location(x=40, y=-10, z=1), carla.Rotation(yaw=90)))
    if actor is None:
        raise RuntimeError('Native passenger spawn failed')
    return actor


def control(actor, carla, frame, approach_frames):
    if type(frame) is not int or type(approach_frames) is not int or \
            frame < 0 or approach_frames <= 0:
        raise ValueError('Invalid passenger control frame')
    moving = approach_frames <= frame < approach_frames + 60
    actor.apply_control(carla.WalkerControl(
        direction=carla.Vector3D(0, 1, 0), speed=1.0 if moving else 0.0,
        jump=False))
    return {'frame': frame, 'requested_walking': moving,
            'source_kind': 'controller_request'}
