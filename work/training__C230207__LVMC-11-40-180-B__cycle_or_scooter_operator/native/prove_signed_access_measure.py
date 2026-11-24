"""Two controlled 600-frame riding traces and source rejection checks."""
import hashlib
import json
from pathlib import Path
import tempfile

from signed_access_measure import CAMERAS, FRAME_COUNT, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, enters):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample',
             'actor_kind': 'electric_scooter', 'surface_kind': 'roadway',
             'prohibition_sign_erected': True, 'sign_prohibits_actor': True,
             'governed_x_interval_m': [0, 20],
             'sign_text': 'NO BICYCLES, E-BICYCLES OR E-SCOOTERS',
             'director_consultation_source': 'unverified'}
    frames = [{'frame': i, 'elapsed_s': i / 20,
               'camera_ids': list(CAMERAS),
               'actor_x_m': -10 + i * 0.05 if enters else -30 + i * 0.02,
               'actor_speed_mps': 1.0 if enters else 0.4,
               'riding_machine': True} for i in range(FRAME_COUNT)]
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
                                     prefix='c230207-signed-access-') as temp:
        root = Path(temp)
        outside = root / 'witness_1'
        inside = root / 'witness_2'
        no = write_case(outside, False)
        yes = write_case(inside, True)
        if no['inside_governed_segment_frames'] != 0 or no['first_inside_frame'] is not None:
            raise AssertionError('Outside route entered prohibited segment')
        if yes['inside_governed_segment_frames'] != 400 or yes['first_inside_frame'] != 200:
            raise AssertionError('Inside route failed segment entry')
        reject(inside, 'setup.json',
               lambda x: x.update(prohibition_sign_erected=False),
               'Erected prohibition sign source missing')
        reject(inside, 'setup.json',
               lambda x: x.update(actor_kind='motor_vehicle'),
               'Covered machine source missing')
        reject(inside, 'setup.json',
               lambda x: x.pop('governed_x_interval_m'),
               'Sign-governed interval source missing')
        reject(inside, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete riding history')
        reject(inside, 'raw-frames.json',
               lambda x: x[250].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(inside, 'raw-frames.json',
               lambda x: x[250].update(riding_machine=False),
               'Riding state source missing')
        return {'format': 'c230207-signed-access-source-proof-v1', 'passed': True,
                'frames_per_case': FRAME_COUNT,
                'cases': {'witness_1': {'measurement': no,
                                        'setup_sha256': sha(outside / 'setup.json'),
                                        'raw_sha256': sha(outside / 'raw-frames.json')},
                          'witness_2': {'measurement': yes,
                                        'setup_sha256': sha(inside / 'setup.json'),
                                        'raw_sha256': sha(inside / 'raw-frames.json')}},
                'missing_source_negatives': 6, 'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
