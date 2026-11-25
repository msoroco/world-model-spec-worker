"""Add a source-gated passenger-position fallback for four-view occlusion risk."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(HERE.name + '__')
        construction = json.loads((HERE / entry['construction']).read_text())
        scene_file = next(item for item in construction['files'] if item['path'] == 'scene.json')
        scene = json.loads(scene_file['content'])
        if scene['source_kind'] != 'synthetic_diagnostic_fixture':
            raise ValueError('fallback builder requires diagnostic source')
        scene['zone']['passenger_anchor'][1] -= 0.5
        scene_file['content'] = json.dumps(scene, indent=2) + '\n'
        target = HERE / ('construction-fallback1-' + name + '.json')
        target.write_text(json.dumps(construction, indent=2) + '\n')
        candidate = {'id': 'fallback1', 'construction': target.name,
                     'construction_sha256': sha(target),
                     'trigger': {'source': 'original four-view camera frames, marked curb polygon and passenger actor tracks',
                                 'metric': 'simultaneous visibility of curb marking, stopped ego and passenger interaction',
                                 'failure_condition': 'primary camera frames do not show the marked zone and relevant passenger interaction together through the original event window'},
                     'changed_knobs': ['passenger anchor shifted 0.5 m toward the same marked curb pose; zone, ego pose, regulation clock, case conduct, camera profile and duration unchanged'],
                     'offline': {}, 'compatibility': {}}
        entry['candidates'] = [candidate]
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
