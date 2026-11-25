"""Create source-labeled diagnostic approach stabilization fallbacks."""
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
        name = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        scene_file = next(item for item in construction['files'] if item['path'] == 'scene.json')
        scene = json.loads(scene_file['content'])
        if scene['source_kind'] != 'synthetic_diagnostic_fixture':
            raise ValueError('fallback builder requires diagnostic source')
        original_start = scene['bus_route_xy'][0]
        scene['bus_route_xy'][0] = [original_start[0] - 2.0, original_start[1]]
        scene_file['content'] = json.dumps(scene, indent=2) + '\n'
        target = HERE / ('construction-fallback1-' + name + '.json')
        target.write_text(json.dumps(construction, indent=2) + '\n')
        candidate = {'id': 'fallback1', 'construction': target.name,
                     'construction_sha256': sha(target),
                     'trigger': {'source': 'original 900-frame bus speed and front-wheel trace',
                                 'metric': 'stopped-loading stabilization and wheel-curb interval',
                                 'failure_condition': 'primary approach misses a sustained stopped-loading interval or observed wheel-curb interval is indeterminate'},
                     'changed_knobs': ['bus approach spawn shifted 2 m upstream; terminal curb distance, loading activity and separate traffic route unchanged'],
                     'offline': {}, 'compatibility': {}}
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'The bus may overshoot the narrow curb target or fail to stabilize for 20 consecutive stopped-loading frames; an upstream approach gives more settling distance. Original capture must decide whether the measurable trigger occurred.'}
        entry['candidates'] = [candidate]
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
