"""Fourteen synthetic source shapes for hydrant distance and exception contexts."""
import hashlib
import json
from pathlib import Path
import tempfile

from hydrant_measure import CAMERAS, FRAME_COUNT, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = [('witness_1', 'angle_permitted', 21.0, None, False),
         ('witness_2', 'angle_permitted', 19.0, None, False)]
for index, key in enumerate(('traffic_conflict_necessity', 'lawful_direction',
                             'officer_or_device_direction'), 1):
    CASES.extend([(f'exception_{index}_1', 'angle_permitted', 19.0, key, False),
                  (f'exception_{index}_2', 'angle_permitted', 19.0, key, True)])
for prefix, regime, distances in [('numeric_1', 'parallel_permitted', (14.5, 15, 15.5)),
                                  ('numeric_2', 'angle_permitted', (19.5, 20, 20.5))]:
    CASES.extend((f'{prefix}_{i}', regime, distance, None, False)
                 for i, distance in enumerate(distances))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, regime, distance, exception_key, exception_present):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample',
             'parking_permission_source': regime, 'hydrant_point_ft': [0, 0],
             'distance_uncertainty_ft': 0.1,
             'painted_red': False, 'hydrant_sign_posted': False,
             'property_kind': 'private_public_access',
             'exception_context_declarations': ({exception_key: exception_present}
                                                if exception_key else {})}
    frames = [{'frame': i, 'elapsed_s': i / 20, 'camera_ids': list(CAMERAS),
               'ego_speed_mps': 0.0,
               'ego_footprint_ft': [distance, -1, distance + 4, 1]}
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
                                     prefix='c200568-hydrant-') as temp:
        root = Path(temp)
        results = {}
        for suffix, regime, distance, exception_key, exception_present in CASES:
            folder = root / suffix
            measured = write_case(folder, regime, distance, exception_key,
                                  exception_present)
            if measured['stopped_frames'] != FRAME_COUNT:
                raise AssertionError('Stopped interval lost')
            threshold = 15 if regime == 'parallel_permitted' else 20
            expected = 'inside' if distance < threshold else (
                'outside' if distance > threshold else 'overlaps')
            if measured['threshold_relation'] != expected:
                raise AssertionError('Source distance bracket mismatch')
            if exception_key and measured['exception_context_declarations'][exception_key] != exception_present:
                raise AssertionError('Exception context contrast failed')
            results[suffix] = {'measurement': measured,
                               'setup_sha256': sha(folder / 'setup.json'),
                               'raw_sha256': sha(folder / 'raw-frames.json')}
        probe = root / 'no_parking_regime'
        if write_case(probe, 'no_parking_permitted', 19, None, False)['applicable_threshold_ft'] != 20:
            raise AssertionError('No-parking regime should use twenty feet')
        folder = root / 'witness_2'
        reject(folder, 'setup.json',
               lambda x: x.update(parking_permission_source='unknown'),
               'Parking permission source missing')
        reject(folder, 'setup.json', lambda x: x.pop('hydrant_point_ft'),
               'Hydrant source missing')
        reject(folder, 'raw-frames.json', lambda x: x.pop(),
               'Incomplete stopped interval source')
        reject(folder, 'raw-frames.json',
               lambda x: x[50].update(camera_ids=['overview']),
               'Four source camera identities missing')
        reject(folder, 'raw-frames.json',
               lambda x: x[50].update(ego_footprint_ft=None),
               'Vehicle footprint source missing')
        return {'format': 'c200568-hydrant-source-proof-v1', 'passed': True,
                'frames_per_case': FRAME_COUNT, 'planned_cases': results,
                'no_parking_regime_check': True, 'missing_source_negatives': 5,
                'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
