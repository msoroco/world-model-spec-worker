"""Test 600-frame original source joins and fail-closed missing-source branches."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from native_red import CAMERAS, CONDITIONS, FRAMES, plan, sha
from prove_native_red import rows_for
from source_join import full_decode, join_capture, join_original

HERE = Path(__file__).resolve().parent


def reject(action, expected):
    try:
        action()
    except (ValueError, KeyError) as exc:
        if expected not in str(exc):
            raise AssertionError('Wrong rejection: ' + str(exc)) from exc
        return
    raise AssertionError('Missing negative-source rejection: ' + expected)


def fixture(config):
    samples = rows_for(config)
    frame_map, cameras = [], []
    pixels = {name: format(index + 1, '064x') for index, (name, _, _, _) in enumerate(CAMERAS)}
    for index, row in enumerate(samples):
        frame, time_s = index + 100, index / 20
        row.update(native_frame=frame, time_s=time_s, source_rgb_sha256=pixels)
        frame_map.append({'video_frame': index, 'carla_frame': frame,
                          'native_frame': frame, 'time_s': time_s,
                          'source_rgb_sha256': pixels})
        for name, width, height, _ in CAMERAS:
            cameras.append({'camera': name, 'video_frame': index,
                            'native_frame': frame, 'time_s': time_s,
                            'width': width, 'height': height,
                            'source_path': name + '.mkv',
                            'source_rgb_sha256': pixels[name]})
    return samples, frame_map, cameras


def main():
    checks = []
    negative = 0
    for condition in CONDITIONS:
        config = plan(condition)
        samples, mapping, cameras = fixture(config)
        result = join_original(samples, mapping, cameras, config)
        assert result['frames'] == FRAMES and result['camera_rows'] == 4 * FRAMES
        trace = [{'frame': row['native_frame'], 'time_s': row['time_s'],
                  'red_entry_source': {key: value for key, value in row.items()
                                       if key != 'source_rgb_sha256'}} for row in samples]
        evidence = [{'original_frame': row['native_frame'],
                     'recording_time_s': row['time_s'], 'actor_id': row['walker_id']}
                    for row in samples]
        assert join_capture(samples, trace, evidence)['trace_evidence_join_passed']
        reject(lambda: join_capture(samples, trace[:-1], evidence), 'Incomplete original pedestrian capture streams')
        negative += 1
        bad_trace = copy.deepcopy(trace)
        bad_trace[100]['red_entry_source']['traffic']['state'] = 'Green'
        reject(lambda: join_capture(samples, bad_trace, evidence), 'Original pedestrian trace source differs')
        negative += 1
        bad_evidence = copy.deepcopy(evidence)
        bad_evidence[100]['actor_id'] += 1
        reject(lambda: join_capture(samples, trace, bad_evidence), 'Original pedestrian capture identity differs')
        negative += 1
        checks.append({'case_id': config['case_id'], 'join': result})
        reject(lambda: join_original(samples, mapping[:-1], cameras, config), 'Incomplete original')
        negative += 1
        bad = copy.deepcopy(mapping)
        bad[200]['carla_frame'] += 1
        reject(lambda: join_original(samples, bad, cameras, config), 'FrameMap identity differs')
        negative += 1
        bad = copy.deepcopy(cameras)
        bad[0]['source_rgb_sha256'] = '0' * 64
        reject(lambda: join_original(samples, mapping, bad, config), 'pixel/frame source differs')
        negative += 1
        bad = copy.deepcopy(samples)
        bad[220]['other']['state'] = 'walk' if config['requested_other_device'] != 'walk' else 'dont_walk'
        expected = ('Countdown original-source program differs' if condition == 'exception_countdown'
                    else 'changed red-entry source')
        reject(lambda: join_original(bad, mapping, cameras, config), expected)
        negative += 1
    scratch_root = Path(os.environ['TMPDIR'])
    if scratch_root.name != '.runtime-work':
        raise ValueError('CPU media fixture scratch must be under .runtime-work')
    with tempfile.TemporaryDirectory(prefix='c111331-red-source-', dir=scratch_root) as temp:
        video = Path(temp) / 'source.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20:d=30',
                        '-c:v', 'ffv1', str(video)], check=True)
        decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
                                  '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
                                 capture_output=True, check=True).stdout
        assert len(decoded) == FRAMES * 16 * 16 * 3
        hashes = [hashlib.sha256(decoded[index * 768:(index + 1) * 768]).hexdigest()
                  for index in range(FRAMES)]
        assert full_decode(video, 16, 16, hashes)['full_decode'] is True
        damaged = list(hashes)
        damaged[100] = '0' * 64
        reject(lambda: full_decode(video, 16, 16, damaged), 'Decoded original RGB pixels differ')
        negative += 1
    receipt = {'format': 'c111331-red-original-join-cpu-proof-v1',
               'positive_checks': len(checks) + 1, 'negative_checks': negative,
               'case_results': checks, 'source_join_sha256': sha(HERE / 'source_join.py'),
               'fixture_is_synthetic': True, 'native_executed': False,
               'full_video_decode_tested': True,
               'full_video_fixture_dimensions': [16, 16],
               'legal_verdict_claimed': False}
    output = HERE.parent / 'native-red-source-join-proof.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'positive_checks': len(checks) + 1, 'negative_checks': negative,
                      'receipt_sha256': sha(output)}, sort_keys=True))


if __name__ == '__main__':
    main()
