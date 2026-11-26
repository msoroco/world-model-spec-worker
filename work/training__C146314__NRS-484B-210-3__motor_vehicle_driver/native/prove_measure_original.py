"""Source-shaped CPU positives and corrupt-source negatives for saved pass measurement."""
import copy
import hashlib
import json
from pathlib import Path

from measure_original import measure


def body(x, y, actor_id):
    corners = [[x + dx, y + dy] for dx in (-2.25, 2.25)
               for dy in (-.9, .9)]
    return {'actor_id': actor_id, 'body_xy_m': corners}


def rows(lead_y, ego_y):
    road_sha = 'a' * 64
    motion, frames = [], []
    for i in range(600):
        frame, time = 1000 + i, i / 20
        motion.append({'video_frame': i, 'native_frame': frame, 'time_s': time,
                       'source_kind': 'synthetic_cpu_pass', 'native_map_sha256': road_sha,
                       'paved_right_edge_y_m': -8.0,
                       'ego': body(i * .4, ego_y, 1),
                       'lead': body(20 + i * .25, lead_y, 2)})
        frames.append({'video_frame': i, 'carla_frame': frame, 'time_s': time})
    return motion, frames, road_sha


def reject(motion, frames, road_sha, edit, expected):
    changed_motion, changed_frames = copy.deepcopy(motion), copy.deepcopy(frames)
    edit(changed_motion, changed_frames)
    try:
        measure(changed_motion, changed_frames, road_sha)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Corrupt saved source was accepted')


def run():
    measured, negatives = {}, {}
    for name, lead_y, ego_y in [('probe_a', -2.0, -6.0),
                                ('probe_b', -6.0, -8.7)]:
        motion, frames, road_sha = rows(lead_y, ego_y)
        result = measure(motion, frames, road_sha)
        assert result['pass_complete'] and result['right_pass_overlap_frames'] > 0
        assert (result['off_paved_right_pass_overlap_frames'] > 0) == (name == 'probe_b')
        assert result['right_pass_requires_off_pavement_geometry'] == (name == 'probe_b')
        measured[name] = result
        negatives[name] = {
            'map_hash': reject(motion, frames, road_sha,
                               lambda m, f: m[1].update(native_map_sha256='b' * 64),
                               'road source hash differs'),
            'missing_lead': reject(motion, frames, road_sha,
                                   lambda m, f: m[1].pop('lead'),
                                   'Two distinct original vehicle sources required'),
            'frame_gap': reject(motion, frames, road_sha,
                                lambda m, f: f[1].update(carla_frame=5000),
                                'frame map differs')}
    script = Path(__file__).with_name('measure_original.py')
    proof = {'format': 'c146314-original-pass-measure-cpu-proof-v1',
             'measure_source_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
             'positives': measured, 'negatives': negatives,
             'physical_native_verified': False, 'legal_verdict': None}
    path = Path(__file__).with_name('measure-proof.json')
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'proof_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'positives': len(measured), 'negatives': sum(map(len, negatives.values()))}


if __name__ == '__main__':
    print(json.dumps(run()))
