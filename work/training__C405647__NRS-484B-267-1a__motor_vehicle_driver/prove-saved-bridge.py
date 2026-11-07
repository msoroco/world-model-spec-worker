"""Synthetic CPU integration proof for Native-frame to saved-measurement bridge."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from geometry import requested_tracks, synthetic_subject_body_xy
from prepare_saved import prepare


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _source(folder, case):
    folder.mkdir()
    raw, videos, annotations = [], [], []
    for request in requested_tracks(case):
        index = request['frame']
        native_frame = 1000 + index
        subject = request['subject_request']
        approach = request['approach_request']
        body = synthetic_subject_body_xy(subject)
        raw.append({'frame': index, 'native_frame': native_frame,
                    'time_s': .05 + index / 20, 'source_kind': 'synthetic_cpu',
                    'front_red_flash_on': None,
                    'special1_requested': request['lamp_request']['front_red_flash_on'],
                    'actors': {
                        'subject': {'native_center_xy_m': [subject['x_m'], -subject['y_m']],
                                    'native_body_xy_m': [[x, -y] for x, y in body]},
                        'approach': {'native_center_xy_m': [approach['x_m'], -approach['y_m']]}}})
        videos.append({'video_frame': index, 'native_frame': native_frame,
                       'time_s': .05 + index / 20})
        annotations.append({'video_frame': index, 'native_frame': native_frame,
                            'front_red_flash_on': request['lamp_request']['front_red_flash_on']})
    _write_rows(folder / 'observed-actors.jsonl', raw)
    _write_rows(folder / 'video-frames.jsonl', videos)
    (folder / 'front_lamp.source').write_text('synthetic CPU lamp pixel placeholder ' + case + '\n')
    video_sha = hashlib.sha256((folder / 'front_lamp.source').read_bytes()).hexdigest()
    (folder / 'front-lamp-review.json').write_text(json.dumps({
        'source_kind': 'synthetic_cpu', 'source_video_sha256': video_sha,
        'frames': annotations}, sort_keys=True) + '\n')


def _mutate_jsonl(path, index, mutation):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutation(rows[index])
    _write_rows(path, rows)


def _negative(scratch, source, name, mutation, expected, case):
    changed = scratch / (case + '-' + name)
    shutil.copytree(source, changed)
    mutation(changed)
    try:
        prepare(changed, scratch / (case + '-' + name + '-out'), case)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError('Wrong rejection: ' + str(error)) from error
    else:
        raise AssertionError('Expected rejection: ' + expected)


def prove():
    results = []
    with tempfile.TemporaryDirectory(prefix='c405647-saved-bridge-') as temporary:
        scratch = Path(temporary)
        for case in ('witness_1', 'witness_2'):
            source = scratch / (case + '-source')
            _source(source, case)
            output = scratch / (case + '-output')
            result = prepare(source, output, case)
            value = result['measurement']
            assert result['source_kind'] == 'synthetic_cpu' and result['frames'] == 480
            assert value['catchup_frame'] == 182
            assert value['first_full_body_inner_lane_clearance_frame'] == (
                81 if case == 'witness_1' else None)
            assert value['vehicle_authority_verified'] is False
            assert value['lamp_qualification_verified'] is False
            _negative(scratch, source, 'video',
                      lambda p: (p / 'front_lamp.source').write_text('changed source\n'),
                      'Lamp review video source hash differs', case)
            _negative(scratch, source, 'join',
                      lambda p: _mutate_jsonl(p / 'video-frames.jsonl', 100,
                                              lambda row: row.update(native_frame=99999)),
                      'Native actor/video/lamp frame join differs', case)
            _negative(scratch, source, 'control',
                      lambda p: _mutate_jsonl(p / 'observed-actors.jsonl', 100,
                                              lambda row: row.update(front_red_flash_on=True)),
                      'Raw Native light control substituted for pixel review', case)
            _negative(scratch, source, 'body',
                      lambda p: _mutate_jsonl(p / 'observed-actors.jsonl', 100,
                                              lambda row: row['actors']['subject'].pop('native_body_xy_m')),
                      'Native body footprint absent', case)
            results.append({'case_suffix': case, 'frames': 480,
                            'catchup_frame': value['catchup_frame'],
                            'clearance_frame': value['first_full_body_inner_lane_clearance_frame'],
                            'changed_video_join_control_body_negatives_rejected': True})
    retained = ROOT / 'synthetic-bridge'
    retained.mkdir(exist_ok=True)
    for case in ('witness_1', 'witness_2'):
        folder = retained / case
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        source = folder / 'source'
        _source(source, case)
        output = folder / 'prepared'
        prepare(source, output, case)
        result = next(row for row in results if row['case_suffix'] == case)
        result['retained_actor_frames_sha256'] = hashlib.sha256(
            (output / 'actor-frames.jsonl').read_bytes()).hexdigest()
        result['retained_scope_sha256'] = hashlib.sha256(
            (output / 'source-scope.json').read_bytes()).hexdigest()
    return {'passed': True, 'results': results,
            'scope': 'synthetic CPU join and saved processing only; no original pixels, '
                     'CARLA motion, lamp qualification or legal verdict'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
