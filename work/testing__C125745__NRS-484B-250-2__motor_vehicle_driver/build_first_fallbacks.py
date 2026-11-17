"""Build three distinct CPU fallback constructions for the first stop-sign case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_timing_sweep_point(output, release_frame=48):
    """Materialize an exact CPU timing variant without changing selected fallbacks.

    The returned manifest is a diagnostic offline input. It is not an expanded
    canonical judgment case or evidence of realized Native motion.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    primary = json.loads((HERE / 'construction.json').read_text())
    config = json.loads((HERE / 'config.json').read_text())
    if type(release_frame) is not int or not 0 <= release_frame < config['frames']:
        raise ValueError('Release frame outside planned capture')
    config['other_release_frame'] = release_frame
    site = (HERE / 'site.json').read_text()
    (output / 'site.json').write_text(site)
    emit(output / 'config.json', config)
    construction = copy.deepcopy(primary)
    construction['sweep_point'] = {
        'sweep_id': 'c125745-1', 'axis': 'other_release_frame',
        'commanded_value': release_frame, 'unit': 'Native frame',
        'scope': 'CPU offline construction only; physical timing unverified',
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
    primary = json.loads((HERE / 'construction.json').read_text())
    base_config = json.loads((HERE / 'config.json').read_text())
    base_site = json.loads((HERE / 'site.json').read_text())
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case = manifest['cases'][0]
    candidates = []
    alternatives = [
        ('fallback1', 'other_release_frame', 'The other actor misses the intended close entry interval',
         'Release the other vehicle eight frames earlier while retaining both routes and the ego stop'),
        ('fallback2', 'site.camera_poses.overview', 'The overview camera occludes a stop-sign face or original body entry',
         'Move the overview camera to an alternate elevated corner while retaining the source cameras'),
        ('fallback3', 'capture_duration', 'The ego has not completely cleared the crossing in the planned recording',
         'Extend the synchronized capture by ten seconds without changing vehicle priority control'),
    ]
    for ident, knob, failure, remedy in alternatives:
        config = copy.deepcopy(base_config)
        site = copy.deepcopy(base_site)
        if ident == 'fallback1':
            config['other_release_frame'] = 32
        elif ident == 'fallback2':
            site['camera_poses']['overview'] = [28, -22, 12, 135, -20, 0]
        else:
            config['frames'] = 1100
            config['duration_s'] = 55
        site_path = HERE / f'{ident}-site.json'
        config_path = HERE / f'{ident}-config.json'
        emit(site_path, site)
        config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
        emit(config_path, config)
        construction = copy.deepcopy(primary)
        construction['fallback_design'] = {'trigger': failure, 'changed_knob': knob,
                                           'remedy': remedy,
                                           'scope': 'synthetic CPU construction; physical acceptance unclaimed'}
        if ident == 'fallback3':
            construction['termination_rules'] = ['1100 synchronized frames; seal only after encoder closure and restoration']
        for file in construction['files']:
            if file['path'] == 'config.json':
                file['source'] = str(config_path.relative_to(ROOT))
                file['content'] = config_path.read_text()
            elif file['path'] == 'site.json':
                file['source'] = str(site_path.relative_to(ROOT))
                file['content'] = site_path.read_text()
        construction_path = HERE / f'{ident}-construction.json'
        emit(construction_path, construction)
        candidates.append({'id': ident, 'construction': construction_path.name,
                           'construction_sha256': sha(construction_path),
                           'trigger': {'source': 'retained original Native capture and four source-camera streams',
                                       'metric': knob, 'failure_condition': failure},
                           'changed_knobs': [knob],
                           'remedy': remedy})
    case['candidates'] = candidates
    emit(manifest_path, manifest)
    return {c['id']: c['construction_sha256'] for c in candidates}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
