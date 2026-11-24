"""Four case-shaped 600-frame cycle passing traces and negative checks."""
import hashlib
import json
from pathlib import Path
import tempfile

from cycle_pass_measure import CAMERAS, FRAME_COUNT, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = [('witness_1', True, True, True),
         ('witness_2', False, True, True),
         ('exception_1_1', False, True, True),
         ('exception_1_2', False, False, True)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, moves_left, available, safe):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample', 'cycle_kind': 'bicycle',
             'same_direction_lane_count': 2, 'right_lane_id': 'right',
             'immediate_left_lane_id': 'left', 'left_lane_available': available,
             'left_move_reasonably_safe': safe,
             'availability_source_authority': 'synthetic_fixture_only'}
    frames = [{'frame': i, 'elapsed_s': i / 20, 'camera_ids': list(CAMERAS),
               'ego_x_m': -20 + i * 0.1, 'cycle_x_m': i * 0.05,
               'ego_heading': '+x', 'cycle_heading': '+x',
               'ego_lane_id': 'left' if moves_left and i >= 300 else 'right'}
              for i in range(FRAME_COUNT)]
    (folder / 'setup.json').write_text(json.dumps(setup, sort_keys=True) + '\n')
    (folder / 'raw-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
    return derive(folder)


def reject(folder, file_name, mutate, expected):
    p = folder / file_name
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
                                     prefix='c247014-cycle-pass-') as temp:
        root = Path(temp)
        results = {}
        for suffix, moves_left, available, safe in CASES:
            folder = root / suffix
            measured = write_case(folder, moves_left, available, safe)
            if measured['pass_first_frame'] != 320 or measured['pass_last_frame'] != 480:
                raise AssertionError('Longitudinal pass changed across cases')
            expected = measured['pass_frames'] if moves_left else 0
            if measured['ego_immediate_left_lane_during_pass_frames'] != expected:
                raise AssertionError('Immediate-left-lane pass contrast failed')
            if moves_left and measured['first_immediate_left_lane_frame'] >= measured['pass_first_frame']:
                raise AssertionError('Lane change did not precede pass')
            results[suffix] = {'measurement': measured,
                               'setup_sha256': sha(folder / 'setup.json'),
                               'raw_sha256': sha(folder / 'raw-frames.json')}
        # The other limb of the exception is separately exercised without a new case claim.
        unsafe = write_case(root / 'unsafe_move_diagnostic', False, True, False)
        if unsafe['left_move_reasonably_safe_declaration'] is not False:
            raise AssertionError('Unsafe-move alternative lost')
        folder = root / 'witness_1'
        reject(folder, 'setup.json', lambda x: x.update(cycle_kind='motorcycle'),
               'Covered cycle source missing')
        reject(folder, 'setup.json', lambda x: x.update(same_direction_lane_count=1),
               'Multiple same-direction lanes source missing')
        reject(folder, 'setup.json', lambda x: x.pop('left_lane_available'),
               'Left-lane availability source missing')
        reject(folder, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete same-direction pass history')
        reject(folder, 'raw-frames.json',
               lambda x: x[400].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(folder, 'raw-frames.json',
               lambda x: x[400].update(cycle_heading='-x'),
               'Same-direction source missing')
        return {'format': 'c247014-cycle-pass-source-proof-v1', 'passed': True,
                'frames_per_case': FRAME_COUNT, 'cases': results,
                'unsafe_move_alternative_checked': True,
                'missing_source_negatives': 6, 'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
