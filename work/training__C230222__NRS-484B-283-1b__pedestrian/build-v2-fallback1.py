"""Add a distinct same-case curb spawn fallback to each 600-frame diagnostic."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'v2-primary-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((HERE / entry['construction']).read_text())
        fallback = copy.deepcopy(primary)
        config_file = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = 'fallback1'
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        fallback['status'] = 'unselected_current_runtime_curb_spawn_fallback'
        target = HERE / 'v2-fallback1' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original Native walker spawn can overlap curb geometry; source-measured initial footprint clearance decides the fallback.'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': str(target.relative_to(HERE)),
            'construction_sha256': sha(target),
            'trigger': {
                'source': 'original_native_pedestrian_footprint_and_road_edge',
                'metric': 'native_initial_footprint_clearance_m_below',
                'failure_condition': 'native_initial_footprint_clearance_m_below 1.25'},
            'changed_knobs': ['pedestrian spawn and two-meter pre-roll']}]
    manifest['status'] = 'unselected_current_runtime_primary_and_fallback_cpu_proof'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'fallbacks': 2}))


if __name__ == '__main__':
    main()
