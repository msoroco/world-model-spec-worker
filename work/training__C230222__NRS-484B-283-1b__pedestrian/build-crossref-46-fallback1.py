"""Add source-triggered curb spawn fallback to the two school-warning survey cases."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'crossref-46-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].split('__crossref_lvmc_11_46_030_', 1)[1]
        fallback = copy.deepcopy(json.loads((HERE / entry['construction']).read_text()))
        engineering = next(item for item in fallback['files'] if item['path'] == 'engineering.py')
        engineering['content'] = engineering['content'].replace("or ident != 'primary':", "or ident not in IDS:")
        config_file = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config['candidate_id'] = 'fallback1'
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        fallback['status'] = 'unselected_survey_gated_curb_spawn_fallback'
        target = HERE / 'crossref-46-fallback1' / label / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original Native walker spawn may overlap curb geometry; source-measured initial footprint clearance chooses the same spawn/pre-roll fallback in both school-warning contexts.'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': str(target.relative_to(HERE)),
            'construction_sha256': digest(target),
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
