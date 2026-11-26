"""Prepare same-case earlier-start fallback for measurable feature reach risk."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads((HERE / 'selected-compatibility-manifest.json').read_text())
    for suffix, entry in zip(SUFFIXES, selected['cases']):
        if entry['case_id'].rsplit('__', 1)[-1] != suffix:
            raise ValueError('Selected case order changed')
        primary = json.loads((HERE / entry['construction']).read_text())
        candidate = copy.deepcopy(primary)
        config_file = next(item for item in candidate['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        if config['ego_spawn']['s_m'] != (300 if 'curve' in suffix else 330) or config['candidate_id'] != 'primary':
            raise ValueError('Unexpected primary feature spawn')
        config['ego_spawn']['s_m'] += 20
        config['candidate_id'] = 'fallback1'
        config_file['content'] = encode(config)
        candidate['status'] = 'selected_fallback_cpu_construction'
        candidate['measurement_plan']['status'] = 'cpu_prepared_original_native_unobserved'
        candidate['mechanisms'].append('Ego starts 20 m closer to feature; exact feature, lanes and comparison variable retained')
        path = HERE / 'selected-constructions' / suffix / 'fallback1/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encode(candidate))
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'The original Native ego may not reach the authored crest or curve interval during its left-side controller phase; inspect source-frame body and map positions.'}
        entry['fixture_recipe'] = ('work/' + HERE.name + '/selected-fallback-fixtures/' +
                                   suffix + '/fixture-recipe.json')
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {
                'source': 'original Native ego body, map waypoint and 600-frame time join',
                'metric': 'feature approach or traversal frame count with the requested body position',
                'failure_condition': 'Primary has no original source frames showing the requested body position at the authored crest or curve interval'},
            'changed_knobs': ['ego spawn moved 20 m closer to feature for every linked comparison case; same feature geometry, controller phases, cameras and duration'] }]
    selected['status'] = 'selected_fallback_offline_pending'
    target = HERE / 'selected-fallback-draft.json'
    target.write_text(encode(selected))
    print(json.dumps({'cases': len(selected['cases']), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
