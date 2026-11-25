"""Promote exact crossing bundles to selected CPU proof candidates."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    draft = json.loads((ROOT / 'draft-route-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    selected = {'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'selected_cpu_proof_in_progress', 'delivery_ready': False,
                'original_native_observed': False, 'cases': []}
    description = None
    proposal_cases = []
    for suffix, condition in (('a', 'right_angle'), ('b', 'longer_diagonal')):
        case_id = next(case['case_id'] for case in plan['cases'] if case['case_id'].endswith('condition_' + suffix))
        source = ROOT / 'draft-route' / ('condition_' + suffix) / 'construction.json'
        primary = json.loads(source.read_text())
        primary['status'] = 'selected_cpu_proof_in_progress'
        primary['measurement_plan']['status'] = 'selected_cpu_proof_in_progress'
        p = ROOT / 'selected' / ('condition_' + suffix) / 'primary/construction.json'
        write(p, primary)
        fallback = copy.deepcopy(primary)
        config_item = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_item['content'])
        config['walker_spawn_z_m'] = .65
        config_item['content'] = json.dumps(config, indent=2) + '\n'
        fallback['mechanisms'].append('Pedestrian spawn-height clearance fallback, same route and capture')
        q = ROOT / 'selected' / ('condition_' + suffix) / 'fallback1/construction.json'
        write(q, fallback)
        description = primary['recording_description']
        selected['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(p.relative_to(ROOT)), 'construction_sha256': sha(p),
            'candidates': [{'id': 'fallback1', 'construction': str(q.relative_to(ROOT)),
                            'construction_sha256': sha(q),
                            'trigger': {'source': 'original_native_spawn_and_footprint_clearance',
                                        'metric': 'initial_vertical_ground_clearance_m',
                                        'failure_condition': 'original walker spawn collision or initial clearance below 0.05 m'},
                            'changed_knobs': ['walker_spawn_z_m: 0.5 to 0.65']}],
            'candidate_risk': {'status': 'physical',
                'reason': 'Original walker spawn may overlap the authored curb or road surface; a source-measured initial clearance or collision triggers a higher spawn, with all route conditions fixed.'},
            'measurement_contract': 'measurement-contracts/condition_' + suffix + '.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'worker-analysis-report-v1'},
            'fixture_recipe': str((ROOT / 'diagnostic' / ('condition_' + suffix) / 'recipe.json').relative_to(ROOT.parents[1]))})
        proposal_cases.append({'case_id': case_id, 'target_law_id': 'LVMC-11-30-050',
            'target_type': 'boundary_probe', 'rationale': 'Measure the full outside-crosswalk route with the two statutory alternatives kept disjunctive.',
            'paired_probe_id': 'c230222-crossing-route-pair',
            'deliberate_differences': ['requested_crossing_path_geometry'],
            'probe': {'primary_variable': 'requested_crossing_path_geometry',
                      'comparison_or_standard': 'original pedestrian route and opposite curb',
                      'target_value_or_branch': condition},
            'variable_assignments': {'requested_crossing_path_geometry':
                                     {'kind': 'world_setup', 'value': condition}},
            'unresolved_judgment_calls': [], 'recording_description': description})
    write(ROOT / 'selected-draft-manifest.json', selected)
    baseline = {'case_id': ROOT.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared authored road and curb geometry before route variation.',
                'variable_assignments': {'requested_crossing_path_geometry': {'kind': 'world_setup', 'value': None}},
                'unresolved_judgment_calls': [], 'recording_description': description}
    write(ROOT / 'proposals/cases.json', {'cell_id': 'C230222', 'actor': 'pedestrian',
          'status': 'draft', 'cases': [baseline, *proposal_cases], 'sweep_specs': []})
    print(json.dumps({'selected_draft_manifest_sha256': sha(ROOT / 'selected-draft-manifest.json'),
                      'case_count': len(selected['cases'])}))


if __name__ == '__main__':
    main()
