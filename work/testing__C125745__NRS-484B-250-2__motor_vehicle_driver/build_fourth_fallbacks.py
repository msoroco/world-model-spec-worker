"""Build three distinct opposite-turn stop-sign CPU fallback constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_opposite_left_turn'


def emit(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    construction = json.loads((HERE / 'fourth-construction.json').read_text())
    config = json.loads((HERE / 'fourth-config.json').read_text())
    site = json.loads((HERE / 'fourth-site.json').read_text())
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    case = next(entry for entry in manifest['cases'] if entry['case_id'] == CASE)
    designs = [
        ('fallback1', 'site.approaches.other.route_xy_m',
         'The left-turn exit clips the synthetic median-opening clearance',
         'Extend the other vehicle southbound exit along its reviewed route'),
        ('fallback2', 'other_release_frame',
         'Opposite-direction arrival conflicts with the ego stopped approach',
         'Release the other vehicle six frames later'),
        ('fallback3', 'site.camera_poses.reference_corner',
         'The turn intention or governing sign is occluded in corner-camera pixels',
         'Move the reference-corner camera to an elevated opposite view'),
    ]
    candidates = []
    for ident, knob, failure, remedy in designs:
        new_config = copy.deepcopy(config)
        new_site = copy.deepcopy(site)
        if ident == 'fallback1':
            new_site['approaches']['other']['route_xy_m'][-1] = [15, -20]
        elif ident == 'fallback2':
            new_config['other_release_frame'] = 46
        else:
            new_site['camera_poses']['reference_corner'] = [25, 18, 12, -145, -20, 0]
        prefix = f'fourth-{ident}'
        site_path = HERE / f'{prefix}-site.json'
        config_path = HERE / f'{prefix}-config.json'
        emit(site_path, new_site)
        new_config['site_packet'] = {'path': 'site.json', 'sha256': sha(site_path)}
        emit(config_path, new_config)
        new_construction = copy.deepcopy(construction)
        new_construction['fallback_design'] = {
            'trigger': failure, 'changed_knob': knob, 'remedy': remedy,
            'scope': 'synthetic CPU construction; physical acceptance unclaimed'}
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
