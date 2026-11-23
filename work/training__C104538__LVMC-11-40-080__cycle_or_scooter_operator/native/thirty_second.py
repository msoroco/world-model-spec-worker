"""30-second rider source plan; synthetic timing proof, never Native evidence."""
import hashlib
import json

from engineering import SIGN, VARIANTS, position

RATE_HZ = 20
FRAMES = 600
KINDS = ('mounted_obey', 'mounted_turn', 'dismounted_turn')


def rows(kind, candidate):
    if kind not in KINDS or candidate not in VARIANTS:
        raise ValueError('Unknown rider source plan')
    variant = VARIANTS[candidate]
    result = []
    for frame in range(FRAMES):
        x, y = position(kind, variant, frame)
        turn = kind != 'mounted_obey' and variant['turn_start_frame'] <= frame <= variant['turn_start_frame'] + 80
        mounted = kind != 'dismounted_turn' or frame < 200
        result.append({'frame': frame, 'time_s': frame / RATE_HZ,
                       'x_m': round(x, 6), 'y_m': round(y, 6),
                       'actor_id': 'rider-1', 'machine_class': 'bicycle',
                       'sign_id': SIGN['id'], 'road_id': SIGN['governs_road'],
                       'approach_lane_id': SIGN['governs_lane'],
                       'mounted': mounted, 'walking_machine': not mounted,
                       'u_turn_active': turn,
                       'source_kind': 'synthetic_timing_plan'})
    return result


def validate(source, kind, candidate):
    variant = VARIANTS[candidate]
    if len(source) != FRAMES or [r.get('frame') for r in source] != list(range(FRAMES)):
        raise ValueError('30-second rider frame inventory incomplete')
    if any(r.get('time_s') != r['frame'] / RATE_HZ for r in source):
        raise ValueError('30-second rider timebase differs')
    if any((r.get('actor_id'), r.get('machine_class'), r.get('sign_id'),
            r.get('road_id'), r.get('approach_lane_id'), r.get('source_kind')) !=
           ('rider-1', 'bicycle', SIGN['id'], SIGN['governs_road'], SIGN['governs_lane'],
            'synthetic_timing_plan') for r in source):
        raise ValueError('Rider/sign/source identity differs')
    if any(r.get('walking_machine') is r.get('mounted') or
           type(r.get('mounted')) is not bool or type(r.get('u_turn_active')) is not bool
           for r in source):
        raise ValueError('Rider posture and machine state contradict')
    turns = [r['frame'] for r in source if r['u_turn_active']]
    if kind == 'mounted_obey':
        if turns or any(not r['mounted'] for r in source):
            raise ValueError('Mounted obey plan contains a turn or dismount')
    else:
        if turns != list(range(variant['turn_start_frame'], variant['turn_start_frame'] + 81)):
            raise ValueError('Turn window differs from construction')
        if kind == 'mounted_turn' and any(not r['mounted'] for r in source):
            raise ValueError('Mounted turn plan dismounts')
        if kind == 'dismounted_turn':
            dismount = next((r['frame'] for r in source if not r['mounted']), None)
            if dismount is None or dismount >= turns[0] or any(r['mounted'] for r in source[dismount:]):
                raise ValueError('Dismount must precede turn and persist')
            if any(r['mounted'] for r in source if r['u_turn_active']):
                raise ValueError('Dismounted turn source remounts during turn')
    return {'frames': FRAMES, 'duration_s': FRAMES / RATE_HZ,
            'first_turn_frame': turns[0] if turns else None,
            'dismount_frame': next((r['frame'] for r in source if not r['mounted']), None),
            'post_turn_frames': FRAMES - (turns[-1] + 1) if turns else None,
            'synthetic_only': True}


def digest(source):
    data = json.dumps(source, separators=(',', ':'), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()
