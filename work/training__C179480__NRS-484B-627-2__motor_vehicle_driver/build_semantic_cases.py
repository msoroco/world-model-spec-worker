"""Bind the four source-visible C179480 drafts into canonical draft stages."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'
CASES = ('reference', 'contrast', 'safe_operation_stop', 'law_required_stop')
VARIABLES = ('roadway_stop_placement', 'other_vehicle_hazard',
             'governing_stop_control', 'ego_stop_controller',
             'following_vehicle_controller')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def assignments(name, binding):
    values = {
        'roadway_stop_placement': 'shoulder_clear' if name == 'contrast' else 'travel_lane_overlap',
        'other_vehicle_hazard': 'designated_source_visible_hazard' if name == 'safe_operation_stop' else 'no_hazard_designated; scoped inventory retained',
        'governing_stop_control': 'designated_surveyed_red_light' if name == 'law_required_stop' else 'no_governing_control_designated; scoped inventory retained',
        'ego_stop_controller': 'source_measured_complete_stop_request',
        'following_vehicle_controller': 'fixed_approach_and_gap_response',
    }
    kinds = {item['name']: item['kind'] for item in binding['variable_parameters']}
    if set(values) != set(kinds) or set(values) != set(VARIABLES):
        raise ValueError('Canonical variable inventory differs from binding')
    return {key: {'kind': kinds[key], 'value': value} for key, value in values.items()}


def build():
    binding = read(PROPOSALS/'bindings.json')
    template = read(PROPOSALS/'template.json')
    draft = read(PROPOSALS/'cases.json')
    old = {case['case_id'].rsplit('__', 1)[-1]: case for case in draft['cases']}
    if set(old) != set(CASES):
        raise ValueError('Four draft cases required')
    entries = []
    baseline = {
        'case_id': HERE.name+'__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared definition only; no baseline recording or legal label selected.',
        'variable_assignments': assignments('reference', binding),
        'recording_description': old['reference']['recording_description'],
    }
    entries.append(baseline)
    differences = {
        'reference': [], 'contrast': ['roadway_stop_placement'],
        'safe_operation_stop': ['other_vehicle_hazard'],
        'law_required_stop': ['governing_stop_control'],
    }
    probes = {
        'reference': ('roadway_stop_placement', 'travel_lane_overlap'),
        'contrast': ('roadway_stop_placement', 'shoulder_clear'),
        'safe_operation_stop': ('other_vehicle_hazard', 'designated_source_visible_hazard'),
        'law_required_stop': ('governing_stop_control', 'designated_surveyed_red_light'),
    }
    for name in CASES:
        source = old[name]
        variable, target = probes[name]
        entries.append({
            'case_id': source['case_id'], 'target_law_id': template['law_id'],
            'target_type': 'judgment_sweep',
            'rationale': source['case_description']+' Original traffic, necessity and compliance judgments remain unresolved.',
            'paired_probe_id': 'c179480-roadway-stop-factored',
            'deliberate_differences': differences[name],
            'probe': {'primary_variable': variable,
                      'comparison_or_standard': 'source-bound physical observation; no legal cutoff',
                      'target_value_or_branch': target},
            'variable_assignments': assignments(name, binding),
            'recording_description': source['recording_description'],
            'unresolved_judgment_calls': [item['phrase'] for item in
                                          template['structure']['judgment_calls_needed']],
        })
    specs = []
    for item in template['structure']['judgment_calls_needed']:
        slug = {'normal and reasonable movement of traffic': 'traffic-effect',
                'necessary for safe operation': 'safe-operation',
                'in compliance with law': 'governing-law'}[item['phrase']]
        specs.append({
            'sweep_id': 'c179480-'+slug+'-pending',
            'target_law_id': template['law_id'],
            'judgment_refs': [item],
            'rationale': 'Qualitative statutory judgment requires original source and independent review, with no invented numeric cutoff.',
            'status': 'incomplete',
            'missing_inputs': [
                'Source-reviewed physical sampling range and comparison isolation',
                'Selected additional cases if original evidence leaves this judgment uncovered',
            ],
        })
    canonical = {'cell_id': binding['cell_id'], 'actor': binding['actor'],
                 'status': 'draft', 'cases': entries, 'sweep_specs': specs,
                 'sweeps_expanded': False}
    write(PROPOSALS/'canonical-cases.json', canonical)
    names = {'relevance_batch': 'relevance_batch.json',
             'relevance': 'relevance.json', 'template': 'template.json',
             'bindings': 'bindings.json', 'cases': 'canonical-cases.json'}
    stages = {key: {'path': 'proposals/'+filename,
                    'sha256': sha(PROPOSALS/filename)} for key, filename in names.items()}
    stages['judgment_observables'] = [
        {'path': 'proposals/judgment_observables_'+slug+'.json',
         'sha256': sha(PROPOSALS/('judgment_observables_'+slug+'.json'))}
        for slug in ('traffic_movement', 'safe_operation', 'legal_compliance')]
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': stages}
    write(PROPOSALS/'semantic-index.json', index)
    return {'cases': len(entries), 'incomplete_sweeps': len(specs),
            'semantic_index_sha256': sha(PROPOSALS/'semantic-index.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
