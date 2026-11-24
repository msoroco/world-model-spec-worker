"""Four 600-frame parked lamp source shapes and missing-source mutations."""
import hashlib
import json
from pathlib import Path
import tempfile

from parked_lamp_measure import CAMERAS, FRAME_COUNT, derive, lamp_command

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = [('witness_1', 'dimmed'), ('witness_2', 'full'),
         ('exception_1_1', 'full'), ('exception_1_2', 'parking')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, mode):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample',
             'nighttime_clock_source': True, 'highway_location_source': True,
             'lawful_parking_review': 'unverified'}
    frames = [{'frame': i, 'elapsed_s': i / 20, 'camera_ids': list(CAMERAS),
               'ego_speed_mps': 0.0, 'lamp_mode_source': mode,
               'lamp_control_request': lamp_command(mode)} for i in range(FRAME_COUNT)]
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
                                     prefix='c229422-parked-lamps-') as temp:
        root = Path(temp)
        rows = {}
        for suffix, mode in CASES:
            folder = root / suffix
            measured = write_case(folder, mode)
            if measured['parked_frames'] != FRAME_COUNT:
                raise AssertionError('Full parked interval lost')
            if (measured['dimmed_headlamp_frames'],
                measured['full_headlamp_frames'],
                measured['cowl_or_parking_lamp_frames']) != (
                    (600 if mode == 'dimmed' else 0),
                    (600 if mode == 'full' else 0),
                    (600 if mode in ('cowl', 'parking') else 0)):
                raise AssertionError('Lamp mode contrast lost')
            rows[suffix] = {'measurement': measured,
                            'setup_sha256': sha(folder / 'setup.json'),
                            'raw_sha256': sha(folder / 'raw-frames.json')}
        if lamp_command('cowl')['cowl_lamps_on'] is not True:
            raise AssertionError('Cowl controller alternative missing')
        try:
            lamp_command('unknown')
        except ValueError:
            pass
        else:
            raise AssertionError('Unknown lamp controller mode accepted')
        folder = root / 'witness_1'
        reject(folder, 'setup.json', lambda x: x.update(nighttime_clock_source=False),
               'Nighttime clock source missing')
        reject(folder, 'setup.json', lambda x: x.update(highway_location_source=False),
               'Highway location source missing')
        reject(folder, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete parked interval source')
        reject(folder, 'raw-frames.json',
               lambda x: x[200].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(folder, 'raw-frames.json',
               lambda x: x[200].update(lamp_mode_source=None),
               'Displayed lamp state source missing')
        return {'format': 'c229422-parked-lamp-source-proof-v1', 'passed': True,
                'cases': rows, 'frames_per_case': FRAME_COUNT,
                'controller_alternative_checks': 2,
                'missing_source_negatives': 5, 'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
