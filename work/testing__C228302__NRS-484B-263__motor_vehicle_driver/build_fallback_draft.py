"""Add a measured-trigger upstream approach fallback for exit-route risk."""
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
        scene['road']['exit_waypoints'][0][0] -= 2.0
        scene_file['content'] = json.dumps(scene, indent=2) + '\n'
        target = HERE / ('construction-fallback1-' + name + '.json')
        target.write_text(json.dumps(construction, indent=2) + '\n')
        candidate = {'id': 'fallback1', 'construction': target.name,
                     'construction_sha256': sha(target),
                     'trigger': {'source': 'original map exit connection, ego spawn readback and 900-frame ego/approaching history',
                                 'metric': 'ego spawn clearance and stable approach before exit interaction',
                                 'failure_condition': 'primary ego spawn obstructed or original trace cannot establish the planned exit interaction'},
                     'changed_knobs': ['ego start shifted 2 m upstream on the same reviewed exit route; authority, highway approaches, headway, policy, camera plan and duration unchanged'],
                     'offline': {}, 'compatibility': {}}
        entry['candidates'] = [candidate]
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
