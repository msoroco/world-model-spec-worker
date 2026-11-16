"""Build three distinct ego-right stop-sign CPU fallback constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_right_near_time'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    construction = json.loads((HERE / 'second-construction.json').read_text())
    config = json.loads((HERE / 'second-config.json').read_text())
    site = json.loads((HERE / 'second-site.json').read_text())
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case = next(entry for entry in manifest['cases'] if entry['case_id'] == CASE)
    candidates = []
    designs = [
        ('fallback1', 'other_release_frame', 'The ego-right entry interval drifts in the Native attempt',
         'Release the other vehicle eight frames earlier with the same southbound route'),
        ('fallback2', 'site.camera_poses.overview', 'The ego-right side or sign face is occluded in overview pixels',
         'Use an elevated alternate overview source camera'),
        ('fallback3', 'capture_duration', 'The ego-right complete body does not clear during the planned recording',
         'Extend synchronized capture to 1100 frames'),
    ]
    for ident, knob, failure, remedy in designs:
        new_config = copy.deepcopy(config)
        new_site = copy.deepcopy(site)
        if ident == 'fallback1':
            new_config['other_release_frame'] = 32
        elif ident == 'fallback2':
            new_site['camera_poses']['overview'] = [28, 22, 12, -135, -20, 0]
        else:
            new_config['frames'] = 1100
            new_config['duration_s'] = 55
        prefix = f'second-{ident}'
        site_path = HERE / f'{prefix}-site.json'
        config_path = HERE / f'{prefix}-config.json'
        emit(site_path, new_site)
        new_config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
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
            elif file['path'] == 'site.json':
                file['source'] = str(site_path.relative_to(ROOT))
                file['content'] = site_path.read_text()
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
