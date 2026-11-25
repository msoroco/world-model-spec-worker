"""Add source-labeled diagnostic upstream spawn fallbacks for physical risk."""
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
        scene['rider_route_xyz_m'][0][0] -= 1.0
        scene_file['content'] = json.dumps(scene, indent=2) + '\n'
        target = HERE / ('construction-fallback1-' + name + '.json')
        target.write_text(json.dumps(construction, indent=2) + '\n')
        candidate = {'id': 'fallback1', 'construction': target.name,
                     'construction_sha256': sha(target),
                     'trigger': {'source': 'original rider spawn/readback and 900-frame body history',
                                 'metric': 'rider spawn clearance and approach stabilization before pedestrian pass',
                                 'failure_condition': 'primary rider spawn is obstructed or approach does not establish a behind-to-ahead pass'},
                     'changed_knobs': ['rider approach start moved 1 m upstream within the reviewed connected sidewalk; signal timing, rider response, pedestrian route and capture contract unchanged'],
                     'offline': {}, 'compatibility': {}}
        entry['candidate_risk'] = {'status': 'physical',
                                   'reason': 'Rider spawn may collide with the pedestrian or leave too little approach for a measured pass; an upstream start can increase clearance only after the original connected sidewalk is reviewed.'}
        entry['candidates'] = [candidate]
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
