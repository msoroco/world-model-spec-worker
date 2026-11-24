"""CPU proof of authored comparison geometry and original-source joins."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from construction import CASES, VIEWS, check_proposals, proposal
from source_join import join


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def fixture():
    digest = hashlib.sha256(b'synthetic-camera-placeholder').hexdigest()
    samples, mapping = [], []
    for i in range(600):
        frame = 2000 + i
        time_s = i / 20
        samples.append({'video_frame': i, 'native_frame': frame, 'time_s': time_s,
                        'pedestrian_id': 17, 'pedestrian_xy_m': [0, -5 + i * .04],
                        'traffic_head_id': 'C111331-facing-circular-head',
                        'pedestrian_head_id': 'C111331-governing-pedestrian-head'})
        mapping.append({'video_frame': i, 'native_frame': frame, 'time_s': time_s,
                        'source_rgb_sha256': {name: digest for name, _, _ in VIEWS}})
    return samples, mapping


def main():
    if not os.environ.get('TMPDIR', '').endswith('c111331-307-2b'):
        raise ValueError('Task-specific scratch directory required')
    construction = check_proposals()
    if len(construction['cases']) != 4 or len({proposal(s)['case_id'] for s in CASES}) != 4:
        raise AssertionError('Four exact case plans required')
    samples, mapping = fixture()
    rejected = []
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        native, frames = root / 'native.jsonl', root / 'frame-map.jsonl'
        def check(a, b):
            write_rows(native, a)
            write_rows(frames, b)
            return join(native, frames)
        positive = check(samples, mapping)
        if positive['source_rgb_bytes_verified'] or positive['legal_verdict'] is not None:
            raise AssertionError('Structural source proof overclaimed physical pixels')
        mutations = {
            'missing_original_frame': (samples[:-1], mapping[:-1]),
            'native_frame_mismatch': (samples, copy.deepcopy(mapping)),
            'missing_camera_hash': (samples, copy.deepcopy(mapping)),
            'missing_pedestrian_pose': (copy.deepcopy(samples), mapping),
            'missing_signal_identity': (copy.deepcopy(samples), mapping),
        }
        mutations['native_frame_mismatch'][1][100]['native_frame'] += 1
        del mutations['missing_camera_hash'][1][100]['source_rgb_sha256']['overview']
        del mutations['missing_pedestrian_pose'][0][100]['pedestrian_xy_m']
        del mutations['missing_signal_identity'][0][100]['traffic_head_id']
        for name, (a, b) in mutations.items():
            try:
                check(a, b)
            except ValueError as exc:
                rejected.append({'case': name, 'error': str(exc)})
            else:
                raise AssertionError(name + ' source omission was accepted')
    receipt = {'format': 'c111331-native-construction-cpu-proof-v1',
               'construction': construction, 'source_join': positive,
               'negative_rejections': rejected,
               'physical_result': None, 'legal_verdict': None}
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
