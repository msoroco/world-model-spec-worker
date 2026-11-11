"""Capture a Native driver-avatar arm pose and frame-joined bone readback."""
from hashlib import sha256
import json
import math
from pathlib import Path

BONES = ('crl_arm__L', 'crl_foreArm__L', 'crl_hand__L')


def _position(transform):
    p = transform.location
    result = [float(p.x), float(p.y), float(p.z)]
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Nonfinite Native hand bone position')
    return result


def pose_left_arm_out(walker, carla):
    """Request a left-arm pose; physical projection remains a later review."""
    original = {name: relative for name, _, _, relative in walker.get_bones().bone_transforms}
    if any(name not in original for name in BONES):
        raise ValueError('Native driver avatar lacks left arm bones')
    edits = []
    for name, roll in (('crl_arm__L', -80.), ('crl_foreArm__L', -25.)):
        value = original[name]
        transform = carla.Transform(value.location, carla.Rotation(
            pitch=value.rotation.pitch, yaw=value.rotation.yaw, roll=value.rotation.roll + roll))
        edits.append((name, transform))
    walker.set_bones(carla.WalkerBoneControlIn(edits))
    walker.blend_pose(1.)


class HandSignalRecorder:
    def __init__(self, path, walker):
        self.path = Path(path)
        self.walker = walker
        self.stream = self.path.open('x')
        self.count = 0
        self.first_frame = None
        self.first_time_s = None

    def append(self, frame, time_s):
        bones = {name: _position(world) for name, world, _, _ in self.walker.get_bones().bone_transforms
                 if name in BONES}
        if set(bones) != set(BONES):
            raise ValueError('Native hand readback omitted arm, forearm or hand')
        if self.first_frame is None:
            self.first_frame = frame
            self.first_time_s = time_s
        if frame != self.first_frame + self.count or abs(time_s - (self.first_time_s + .05 * self.count)) > .001:
            raise ValueError('Native hand bone/frame join differs')
        self.stream.write(json.dumps({'frame': frame, 'time_s': time_s,
                                      'avatar_actor_id': self.walker.id,
                                      'origin': 'native_walker_bone_world_readback',
                                      'bones_world_m': bones}, allow_nan=False) + '\n')
        self.count += 1

    def close(self):
        self.stream.close()
        return sha256(self.path.read_bytes()).hexdigest()


def measure(path, ego_path):
    hands = [json.loads(s) for s in Path(path).read_text().splitlines()]
    egos = [json.loads(s) for s in Path(ego_path).read_text().splitlines()]
    if len(hands) != len(egos) or len(hands) < 3:
        raise ValueError('Original hand and ego frame inventories differ')
    original = []
    for hand, ego in zip(hands, egos):
        if (hand.get('frame'), hand.get('time_s')) != (ego.get('frame'), ego.get('time_s')):
            raise ValueError('Original hand and ego frame join differs')
        if hand.get('origin') != 'native_walker_bone_world_readback' or not isinstance(hand.get('avatar_actor_id'), int):
            raise ValueError('Missing Native hand readback provenance')
        bones = hand.get('bones_world_m')
        if not isinstance(bones, dict) or set(bones) != set(BONES):
            raise ValueError('Missing Native left arm bones')
        for value in bones.values():
            if len(value) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
                raise ValueError('Invalid Native hand bone coordinate')
        original.append({'frame': hand['frame'], 'time_s': hand['time_s'],
                         'hand_world_m': bones['crl_hand__L']})
    return {'frame_count': len(original), 'observations': original,
            'visible_in_pixels': None, 'appropriate_signal_legal_judgment': None}
