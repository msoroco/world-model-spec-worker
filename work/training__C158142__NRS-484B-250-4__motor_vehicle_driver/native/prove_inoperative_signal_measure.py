"""Two controlled source fixtures and negative checks for NRS 484B.250(4)."""
import hashlib
import json
from pathlib import Path
import tempfile

from inoperative_signal_measure import CAMERAS, FRAME_COUNT, choose_stop_reference, derive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_case(folder, stopped):
    folder.mkdir()
    setup = {'source_kind': 'synthetic_native_sample',
             'vehicular_signals_installed_uncovered': True,
             'signal_inoperative_during_entry': True,
             'geometry': {'marked_stop_line_x_m': -5.0, 'near_crosswalk_x_m': -3.0,
                          'nearest_view_point_x_m': -1.0,
                          'intersection_entry_x_m': 0.0},
             'signal_state_authority': 'synthetic_fixture_only'}
    frames = []
    for i in range(FRAME_COUNT):
        if i < 150:
            x, speed = -20 + i * 0.1, 2.0
        elif stopped and i < 190:
            x, speed = -5.0, 0.0
        elif stopped:
            x, speed = -5.0 + (i - 190) / 3, 20 / 3
        else:
            x, speed = -5.0 + (i - 150) / 6, 10 / 3
        frames.append({'frame': i, 'elapsed_s': i / 20,
                       'camera_ids': list(CAMERAS), 'ego_front_x_m': x,
                       'ego_speed_mps': speed,
                       'other_speed_mps': 0.0 if 130 <= i < 145 else 2.0,
                       'other_within_intersection': 160 <= i < 185})
    (folder / 'setup.json').write_text(json.dumps(setup, sort_keys=True) + '\n')
    (folder / 'raw-frames.json').write_text(json.dumps(frames, separators=(',', ':')) + '\n')
    return derive(folder)


def rejection(folder, file_name, mutate, expected):
    path = folder / file_name
    original = path.read_text()
    data = json.loads(original)
    mutate(data)
    path.write_text(json.dumps(data) + '\n')
    try:
        derive(folder)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Unexpected rejection: {error}') from error
    else:
        raise AssertionError(f'Missing rejection: {expected}')
    finally:
        path.write_text(original)


def main():
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c158142-signal-measure-') as temp:
        base = Path(temp)
        stopped = base / 'witness_1'
        rolling = base / 'witness_2'
        yes = write_case(stopped, True)
        no = write_case(rolling, False)
        if not (yes['subject_stop_frame'] == 150 and yes['entry_frame'] == 205
                and yes['other_stop_frame'] == 130 and yes['other_previously_stopped']
                and not yes['other_within_intersection_at_entry']):
            raise AssertionError('Stopped-source ordering failed')
        if not (no['subject_stop_frame'] is None and no['entry_frame'] == 180
                and no['other_within_intersection_at_entry']):
            raise AssertionError('Rolling-source contrast failed')
        if choose_stop_reference({'near_crosswalk_x_m': -3,
                                  'nearest_view_point_x_m': -1})[0] != 'near_crosswalk_x_m':
            raise AssertionError('Crosswalk fallback failed')
        if choose_stop_reference({'nearest_view_point_x_m': -1})[0] != 'nearest_view_point_x_m':
            raise AssertionError('View-point fallback failed')
        rejection(stopped, 'setup.json',
                  lambda x: x.update(signal_inoperative_during_entry=False),
                  'Inoperative signal source missing')
        rejection(stopped, 'setup.json',
                  lambda x: x['geometry'].update(marked_stop_line_x_m=None,
                                                 near_crosswalk_x_m=None,
                                                 nearest_view_point_x_m=None),
                  'No statutory stop reference source')
        rejection(stopped, 'raw-frames.json', lambda x: x.pop(),
                  'Incomplete source frame history')
        rejection(stopped, 'raw-frames.json',
                  lambda x: x[200].update(camera_ids=['overview']),
                  'Four source camera identities missing')
        rejection(stopped, 'raw-frames.json',
                  lambda x: x[130].pop('other_speed_mps'),
                  'Measured pose/speed source missing')
        return {'format': 'c158142-inoperative-signal-source-proof-v1',
                'passed': True, 'frames_per_case': FRAME_COUNT,
                'camera_identities_per_frame': len(CAMERAS),
                'cases': {'witness_1': {'measurement': yes,
                                        'setup_sha256': sha(stopped / 'setup.json'),
                                        'raw_sha256': sha(stopped / 'raw-frames.json')},
                          'witness_2': {'measurement': no,
                                        'setup_sha256': sha(rolling / 'setup.json'),
                                        'raw_sha256': sha(rolling / 'raw-frames.json')}},
                'stop_reference_fallback_checks': 2,
                'missing_source_negatives': 5,
                'native_or_legal_claim': False}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
