"""Build three distinct separated-entry stop-sign CPU fallback constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_left_separated'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_yield_sweep_point(output, hold_frames=16):
    """Build an exact diagnostic hold variant of the separated selected case."""
    output = Path(output)
    config = json.loads((HERE / 'third-config.json').read_text())
    if type(hold_frames) is not int or not 0 <= hold_frames < config['frames']:
        raise ValueError('Hold frames outside planned capture')
    output.mkdir(parents=True, exist_ok=False)
    config['ego_hold_after_clear_frames'] = hold_frames
    emit(output / 'config.json', config)
    construction = json.loads((HERE / 'third-construction.json').read_text())
    construction['sweep_point'] = {
        'sweep_id': 'c125745-2', 'axis': 'ego_hold_after_clear_frames',
        'commanded_value': hold_frames, 'unit': 'Native frame',
        'scope': 'CPU offline construction only; physical yielding unverified',
    }
    for item in construction['files']:
        if item['path'] == 'config.json':
            item['content'] = (output / 'config.json').read_text()
            item.pop('source', None)
    emit(output / 'construction.json', construction)
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': config['assignment_id'],
        'cases': [{'case_id': config['selected_case_id'],
                   'construction': 'construction.json',
                   'construction_sha256': sha(output / 'construction.json')}],
    }
    emit(output / 'execution-manifest.json', manifest)
    return manifest


def build():
    construction = json.loads((HERE / 'third-construction.json').read_text())
    config = json.loads((HERE / 'third-config.json').read_text())
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case = next(entry for entry in manifest['cases'] if entry['case_id'] == CASE)
    designs = [
        ('fallback1', 'ego_hold_after_clear_frames',
         'Controller braking compresses the intended entry separation',
         'Extend ego post-clear hold from eight to twelve frames'),
        ('fallback2', 'other_release_frame',
         'Other vehicle arrives too late for the planned separated ordering',
         'Release the other vehicle six frames earlier'),
        ('fallback3', 'capture_duration',
         'The longer held ego has not completely cleared within the source recording',
         'Extend synchronized capture to 1100 frames'),
    ]
    candidates = []
    for ident, knob, failure, remedy in designs:
        new_config = copy.deepcopy(config)
        if ident == 'fallback1':
            new_config['ego_hold_after_clear_frames'] = 12
        elif ident == 'fallback2':
            new_config['other_release_frame'] = 34
        else:
            new_config['frames'] = 1100
            new_config['duration_s'] = 55
        prefix = f'third-{ident}'
        config_path = HERE / f'{prefix}-config.json'
        emit(config_path, new_config)
        new_construction = copy.deepcopy(construction)
        new_construction['fallback_design'] = {
            'trigger': failure, 'changed_knob': knob, 'remedy': remedy,
            'scope': 'synthetic CPU construction; physical acceptance unclaimed'}
        if ident == 'fallback3':
            new_construction['termination_rules'] = [
                '1100 synchronized frames; seal only after encoder closure and restoration']
        for file in new_construction['files']:
            if file['path'] == 'config.json':
                file['source'] = str(config_path.relative_to(ROOT))
                file['content'] = config_path.read_text()
        path = HERE / f'{prefix}-construction.json'
        emit(path, new_construction)
        candidates.append({'id': ident, 'construction': path.name,
                           'construction_sha256': sha(path),
                           'trigger': {'source': 'retained original Native capture and four source-camera streams',
                                       'metric': knob, 'failure_condition': failure},
                           'changed_knobs': [knob], 'remedy': remedy})
    case['candidates'] = candidates
    emit(manifest_path, manifest)
    return {entry['id']: entry['construction_sha256'] for entry in candidates}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
