"""Exercise C405647 saved-motion processing on CPU synthetic positive/negatives."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from geometry import CASES, requested_tracks, synthetic_subject_body_xy
from measure_saved import measure


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _fixture(folder, case):
    scope = json.loads((ROOT / 'native/source-scope.json').read_text())
    scope['case_suffix'] = case
    scope['coordinate_frame'] = 'authored_opendrive_xy'
    (folder / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
    rows = []
    for request in requested_tracks(case):
        rows.append({'frame': request['frame'], 'time_s': request['time_s'],
                     'subject': request['subject_request'],
                     'subject_body_xy_m': synthetic_subject_body_xy(request['subject_request']),
                     'approach': request['approach_request'],
                     'coordinate_frame': 'authored_opendrive_xy',
                     'front_red_flash_on': request['lamp_request']['front_red_flash_on'],
                     'source_kind': 'synthetic_cpu'})
    _write_rows(folder / 'actor-frames.jsonl', rows)


def _reject(folder, mutation, error_text):
    mutation(folder)
    try:
        measure(folder)
    except ValueError as error:
        if error_text not in str(error):
            raise AssertionError(f'Wrong rejection: {error}') from error
    else:
        raise AssertionError(f'Expected rejection: {error_text}')


def prove():
    results = []
    with tempfile.TemporaryDirectory(prefix='c405647-saved-') as temporary:
        scratch = Path(temporary)
        for case in CASES:
            base = scratch / (case + '-base')
            base.mkdir()
            _fixture(base, case)
            result = measure(base)
            assert result['observed_frame_count'] == 480
            assert result['vehicle_authority_verified'] is False
            assert result['lamp_qualification_verified'] is False
            assert result['legal_immediacy_or_yield_verdict'] is None
            assert result['full_body_cleared_before_catchup'] is (case == 'witness_1')
            negatives = [scratch / (case + '-' + name) for name in
                         ('law', 'lamp', 'time', 'body', 'frame', 'center')]
            for folder in negatives:
                shutil.copytree(base, folder)
            def bad_law(folder):
                path = folder / 'source-scope.json'
                data = json.loads(path.read_text())
                data['assignment_law_text_sha256'] = '0' * 64
                path.write_text(json.dumps(data) + '\n')
            def bad_lamp(folder):
                path = folder / 'actor-frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                for row in rows:
                    row['front_red_flash_on'] = False
                _write_rows(path, rows)
            def bad_time(folder):
                path = folder / 'actor-frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[100]['time_s'] += .05
                _write_rows(path, rows)
            def bad_body(folder):
                path = folder / 'actor-frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                del rows[100]['subject_body_xy_m']
                _write_rows(path, rows)
            def bad_frame(folder):
                path = folder / 'actor-frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[100]['coordinate_frame'] = 'native_carla_xy'
                _write_rows(path, rows)
            def bad_center(folder):
                path = folder / 'actor-frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[100]['subject_body_xy_m'][0][1] += 2
                _write_rows(path, rows)
            _reject(negatives[0], bad_law, 'Law source hash differs')
            _reject(negatives[1], bad_lamp, 'Flashing lamp sequence absent')
            _reject(negatives[2], bad_time, 'Saved frame/time order differs')
            _reject(negatives[3], bad_body, 'Saved subject body footprint absent')
            _reject(negatives[4], bad_frame, 'Saved coordinate frame differs')
            _reject(negatives[5], bad_center, 'Saved subject body center differs')
            results.append({'case_suffix': case, 'frames': 480,
                            'catchup_frame': result['catchup_frame'],
                            'clearance_frame': result['first_full_body_inner_lane_clearance_frame'],
                            'full_body_cleared_before_catchup': result['full_body_cleared_before_catchup'],
                            'law_lamp_time_body_frame_center_negatives_rejected': True})
    return {'passed': True, 'results': results,
            'scope': 'CPU synthetic saved geometry only; no Native, original pixels or legal verdict'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
