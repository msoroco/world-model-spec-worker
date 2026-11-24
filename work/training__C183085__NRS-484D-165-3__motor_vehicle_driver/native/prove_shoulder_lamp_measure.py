"""Eleven controlled 600-frame source shapes and rejection checks."""
import hashlib
import json
from pathlib import Path
import tempfile

from shoulder_lamp_measure import CAMERAS, FRAME_COUNT, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = [('witness_1', None, None, True),
         ('witness_2', None, None, False)]
for axis, prefix, vals in [('ambient_reveal', 'numeric_1', (990, 1000, 1010)),
                          ('front_white_or_amber', 'numeric_2', (495, 500, 505)),
                          ('rear_red', 'numeric_3', (495, 500, 505))]:
    CASES += [(f'{prefix}_{i}', axis, value, True)
              for i, value in enumerate(vals)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, axis, value, lamps_on):
    folder.mkdir()
    estimates = {'ambient_reveal': 990, 'front_white_or_amber': 505,
                 'rear_red': 505}
    if axis is not None:
        estimates[axis] = value
    setup = {'source_kind': 'synthetic_native_sample', 'night_hours_source': True,
             'adjacent_paved_shoulder_source': True, 'passing_traffic_side': 'left',
             'optical_probes': {key: {'estimated_distance_ft': estimate,
                                      'uncertainty_ft': 1}
                                for key, estimate in estimates.items()},
             'optical_source_authority': 'synthetic_fixture_only'}
    frames = [{'frame': i, 'elapsed_s': i / 20, 'camera_ids': list(CAMERAS),
               'ego_speed_mps': 0.0,
               'front_lamp_color': 'white' if lamps_on else 'off',
               'rear_lamp_color': 'red' if lamps_on else 'off',
               'near_traffic_lamp_side': 'left'} for i in range(FRAME_COUNT)]
    (folder / 'setup.json').write_text(json.dumps(setup, sort_keys=True) + '\n')
    (folder / 'raw-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
    return derive(folder)


def reject(folder, name, mutate, expected):
    p = folder / name
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
                                     prefix='c183085-shoulder-lamps-') as temp:
        root = Path(temp)
        results = {}
        for suffix, axis, value, lamps_on in CASES:
            folder = root / suffix
            measured = write_case(folder, axis, value, lamps_on)
            if measured['stopped_frames'] != FRAME_COUNT:
                raise AssertionError('Full stopped interval lost')
            if (measured['front_off_frames'] > 0 or measured['rear_off_frames'] > 0) == lamps_on:
                raise AssertionError('Lamp display contrast failed')
            if axis:
                expected = 'below' if value < (1000 if axis == 'ambient_reveal' else 500) else (
                    'above' if value > (1000 if axis == 'ambient_reveal' else 500) else 'overlaps')
                if measured['optical_brackets'][axis]['threshold_relation'] != expected:
                    raise AssertionError('Numeric bracket contrast failed')
            results[suffix] = {'measurement': measured,
                               'setup_sha256': sha(folder / 'setup.json'),
                               'raw_sha256': sha(folder / 'raw-frames.json')}
        folder = root / 'witness_1'
        reject(folder, 'setup.json', lambda x: x.update(night_hours_source=False),
               'Lighting hours source missing')
        reject(folder, 'setup.json',
               lambda x: x.update(adjacent_paved_shoulder_source=False),
               'Shoulder geometry source missing')
        reject(folder, 'setup.json',
               lambda x: x['optical_probes'].pop('ambient_reveal'),
               'Numeric optical probe source missing')
        reject(folder, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete stopped interval source')
        reject(folder, 'raw-frames.json',
               lambda x: x[200].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(folder, 'raw-frames.json',
               lambda x: x[200].update(front_lamp_color=None),
               'Front lamp source missing')
        return {'format': 'c183085-shoulder-lamp-source-proof-v1',
                'passed': True, 'cases': results, 'frames_per_case': FRAME_COUNT,
                'negative_sources': 6, 'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
