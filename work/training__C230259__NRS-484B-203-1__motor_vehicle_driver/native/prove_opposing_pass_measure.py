"""Two controlled 600-frame opposing passes and missing-source rejections."""
import hashlib
import json
from pathlib import Path
import tempfile

from opposing_pass_measure import CAMERAS, FRAME_COUNT, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, ego_y):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample',
             'traffic_lines_each_direction': 1, 'paved_y_bounds_m': [-4, 4],
             'vehicle_half_width_m': 0.9}
    frames = [{'frame': i, 'elapsed_s': i / 20, 'camera_ids': list(CAMERAS),
               'ego_x_m': -30 + i * 0.1, 'ego_y_m': ego_y,
               'other_x_m': 30 - i * 0.1, 'other_y_m': 2.0,
               'ego_heading': '+x', 'other_heading': '-x'}
              for i in range(FRAME_COUNT)]
    (folder / 'setup.json').write_text(json.dumps(setup, sort_keys=True) + '\n')
    (folder / 'raw-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
    return derive(folder)


def reject(folder, filename, mutate, expected):
    p = folder / filename
    original = p.read_text()
    data = json.loads(original)
    mutate(data)
    p.write_text(json.dumps(data) + '\n')
    try:
        derive(folder)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Unexpected rejection: {error}') from error
    else:
        raise AssertionError(f'Missing rejection: {expected}')
    finally:
        p.write_text(original)


def main():
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c230259-opposing-pass-') as temp:
        root = Path(temp)
        right = root / 'witness_1'
        left = root / 'witness_2'
        yes = write_case(right, -2.0)
        no = write_case(left, 1.5)
        if yes['meeting_frames'] != no['meeting_frames'] or yes['meeting_frames'] < 30:
            raise AssertionError('Opposing meeting did not remain fixed')
        if yes['ego_left_half_during_meeting_frames'] != 0:
            raise AssertionError('Right-side body encroached')
        if no['ego_left_half_during_meeting_frames'] != no['meeting_frames']:
            raise AssertionError('Left-side body contrast absent')
        if yes['other_left_half_during_meeting_frames'] != 0 or no['other_left_half_during_meeting_frames'] != 0:
            raise AssertionError('Opposing vehicle did not retain its right half')
        reject(right, 'setup.json',
               lambda x: x.update(traffic_lines_each_direction=2),
               'Road width/traffic-line source missing')
        reject(right, 'setup.json', lambda x: x.pop('vehicle_half_width_m'),
               'Vehicle body width source missing')
        reject(right, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete opposing approach history')
        reject(right, 'raw-frames.json',
               lambda x: x[300].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(right, 'raw-frames.json',
               lambda x: x[300].update(other_y_m=None),
               'Both vehicle body poses missing')
        reject(right, 'raw-frames.json',
               lambda x: x[300].update(other_heading='+x'),
               'Opposing direction source missing')
        return {'format': 'c230259-opposing-pass-source-proof-v1', 'passed': True,
                'frames_per_case': FRAME_COUNT,
                'cases': {'witness_1': {'measurement': yes,
                                        'setup_sha256': sha(right / 'setup.json'),
                                        'raw_sha256': sha(right / 'raw-frames.json')},
                          'witness_2': {'measurement': no,
                                        'setup_sha256': sha(left / 'setup.json'),
                                        'raw_sha256': sha(left / 'raw-frames.json')}},
                'missing_source_negatives': 6, 'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
