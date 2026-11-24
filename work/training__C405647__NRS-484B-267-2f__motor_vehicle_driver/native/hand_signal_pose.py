"""Request a visible walker arm pose for a source driver or directing officer.

CARLA's unified walker skeleton provides shoulder, arm, forearm and hand bones.
The returned request is not evidence that a driver saw or understood the pose.
"""


def request_bones(carla, side='R'):
    if side not in ('L', 'R'):
        raise ValueError('Select one modeled hand')
    # Parent-relative rotations follow CARLA's WalkerBoneControl contract.
    poses = ((f'crl_shoulder__{side}', (0, 0, -45 if side == 'R' else 45)),
             (f'crl_arm__{side}', (0, 0, -55 if side == 'R' else 55)),
             (f'crl_foreArm__{side}', (0, 0, -35 if side == 'R' else 35)),
             (f'crl_hand__{side}', (0, 90, 0)))
    return [(name, carla.Transform(rotation=carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)))
            for name, (pitch, yaw, roll) in poses]


def apply_hand_signal(carla, walker, side='R'):
    """Submit and read back a custom arm pose; fail if Native lacks the API."""
    transforms = request_bones(carla, side)
    if hasattr(walker, 'set_bones') and hasattr(carla, 'WalkerBoneControlIn'):
        walker.set_bones(carla.WalkerBoneControlIn(transforms))
        if not hasattr(walker, 'show_pose'):
            raise ValueError('Native walker pose blending unavailable')
        walker.show_pose()
    elif hasattr(walker, 'apply_control') and hasattr(carla, 'WalkerBoneControl'):
        control = carla.WalkerBoneControl()
        control.bone_transforms = transforms
        walker.apply_control(control)
    else:
        raise ValueError('Native walker bone-control API unavailable')
    if not hasattr(walker, 'get_bones'):
        raise ValueError('Native walker bone readback unavailable')
    readback = walker.get_bones()
    names = {row.name if hasattr(row, 'name') else row[0] for row in readback.bone_transforms}
    requested = {name for name, _ in transforms}
    if not requested <= names:
        raise ValueError('Native hand-signal bones absent in readback')
    return {'requested_bones': sorted(requested), 'readback_bones': sorted(requested),
            'visual_visibility_verified': False}
