"""Create source-labeled diagnostic approach stabilization fallbacks."""
import hashlib
import json
from pathlib import Path
from math import hypot

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
        original_end = scene['bus_route_xy'][-1]
        dx, dy = original_end[0] - original_start[0], original_end[1] - original_start[1]
        length = hypot(dx, dy)
        if length <= 0:
            raise ValueError('primary approach route degenerate')
        scene['primary_bus_route_xy'] = json.loads(json.dumps(scene['bus_route_xy']))
        scene['bus_route_xy'][0] = [original_start[0] - 2.0 * dx / length,
                                    original_start[1] - 2.0 * dy / length]
        scene_file['content'] = json.dumps(scene, indent=2) + '\n'
        config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = 'fallback1'
        config_file['content'] = json.dumps(config, indent=2) + '\n'
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
