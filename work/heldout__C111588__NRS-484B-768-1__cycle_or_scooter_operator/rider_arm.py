"""Attempt a one-frame visible left-arm gesture on an attached Native walker.

Bone command/readback is separate from source-video visibility and legal signal
appropriateness. The physical rider-bike attachment needs a local CARLA trial.
"""


BONE = 'crl_arm__L'


def _bone(walker):
    for item in walker.get_bones().bone_transforms:
        if item.name == BONE:
            return item
    raise ValueError('Native rider has no left upper-arm bone')


class RiderArm:
    def __init__(self, walker, carla_module):
        self.walker = walker
        self.carla = carla_module
        self.neutral = _bone(walker).relative
        self.raised = False

    def set_signal(self, raised):
        if type(raised) is not bool:
            raise ValueError('Rider signal command must be boolean')
        if raised:
            rotation = self.neutral.rotation
            pose = self.carla.Transform(
                self.neutral.location,
                self.carla.Rotation(pitch=rotation.pitch,
                                    yaw=rotation.yaw,
                                    roll=rotation.roll + 70))
            control = self.carla.WalkerBoneControlIn([(BONE, pose)])
            self.walker.set_bones(control)
            self.walker.blend_pose(1)
        else:
            self.walker.blend_pose(0)
        self.raised = raised

    def readback(self):
        observed = _bone(self.walker).relative.rotation.roll
        return {'bone': BONE, 'commanded_raised': self.raised,
                'relative_roll_deg': float(observed),
                'neutral_relative_roll_deg': float(self.neutral.rotation.roll)}
