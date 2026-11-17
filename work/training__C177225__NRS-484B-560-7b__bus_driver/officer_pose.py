"""Request and record a timed walker arm signal for C177225.

CARLA pose readback establishes only the requested skeleton state. The four
source cameras must still show that the signal was visible to the bus driver.
"""
from officer_direction import OfficerStop


ARM_BONE = 'crl_arm__R'


def _bone_names(walker):
    return {item[0] for item in walker.get_bones().bone_transforms}


def step(walker, carla, signal: OfficerStop, frame: int):
    signal.validate()
    if type(frame) is not int or frame < 0:
        raise ValueError('Native frame must be a nonnegative integer')
    if ARM_BONE not in _bone_names(walker):
        raise ValueError('Native walker lacks required right-arm bone')
    active = signal.first_governing_frame <= frame <= signal.last_governing_frame
    if active:
        if not hasattr(carla, 'WalkerBoneControlIn'):
            raise ValueError('Native CARLA lacks walker bone control API')
        walker.get_pose_from_animation()
        pose = carla.WalkerBoneControlIn([
            (ARM_BONE, carla.Transform(rotation=carla.Rotation(pitch=-90)))])
        walker.set_bones(pose)
        walker.show_pose()
    else:
        walker.hide_pose()
    readback = walker.get_bones()
    if ARM_BONE not in {item[0] for item in readback.bone_transforms}:
        raise ValueError('Walker signal bone disappeared after control')
    return {
        'native_frame': frame,
        'actor_id': signal.officer_id,
        'recipient_actor_id': signal.bus_id,
        'crossing_id': signal.crossing_id,
        'direction': signal.direction,
        'hand_signal': signal.hand_signal,
        'authorized': signal.authorized,
        'authorization_provenance': 'authored_scenario_assumption',
        'governing': active,
        'pose_control_applied': active,
        'pose_bone_readback': ARM_BONE,
        'source_kind': 'original_native_pose_api' if active else 'original_native_pose_api_inactive',
        'visual_comprehension_claimed': False,
    }
