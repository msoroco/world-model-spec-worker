"""Author source-faithful semantic stages without changing public case proposals."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-48-050'
ACTOR = 'heavy_vehicle_driver'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    expected = {item['case_id']: item for item in proposal['cases']}
    relevance = {'cell_id': 'C394566', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                                    'relevance_type': 'specific_match', 'confidence': 'high',
                                    'notes': 'Plausible heavy-vehicle truck-route cell; original weight, district, time and permit authority remain for review.'}],
                 'borderline_excluded': []}
    parameters = [
        ('unladen_weight_lb', 'world_setup', 'original certified unladen vehicle weight in lb'),
        ('truck_route_designation', 'world_setup', 'original authoritative route designation'),
        ('residence_district', 'world_setup', 'original district authority'),
        ('civil_clock_time', 'world_setup', 'original civil timestamp and UTC offset'),
        ('written_permit_status', 'world_setup', 'original written DPW permit status'),
        ('permit_scope_claim', 'world_setup', 'original permit route, time and conditions claim; authority unverified'),
        ('requested_motion', 'controller', 'requested move or stationary contrast')]
    refs = [{'name': name, 'kind': kind, 'range_or_domain': domain} for name, kind, domain in parameters]
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'Vehicle over 8000 lb unladen on a non-truck-route street in a residence district during the 7 p.m. to 6 a.m. window.',
                                             'numeric_conditions': [{'variable': 'unladen_weight_lb', 'operator': '>', 'value': 8000, 'unit': 'lb'}]},
                              'obligation': {'type': 'must_not', 'description': 'Do not operate or move such vehicle under all specified activation conditions, subject to a written special permit.',
                                             'source_clause': 'shall be operated or moved', 'numeric_conditions': []},
                              'exceptions': [{'trigger': 'Special written DPW permit issued upon written application',
                                              'effect': 'The permit may authorize operation or movement in the restricted hours only within actual authority and attached conditions.',
                                              'replacement_obligation': 'Retain original permit, applicant, vehicle, route, time and attached conditions for independent review.',
                                              'source_clause': 'issue a special permit in writing'}],
                              'timing': {'description': 'Between seven p.m. and six a.m.; exact 19:00 and 06:00 endpoints remain unresolved source interpretation.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': refs}
    bindings = {'cell_id': 'C394566', 'actor': ACTOR, 'status': 'draft',
                'established_contexts': [], 'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{**ref, 'used_by_laws': [LAW]} for ref in refs]}
    defaults = {'unladen_weight_lb': 8001, 'truck_route_designation': 'non_truck_route',
                'residence_district': 'residence', 'civil_clock_time': '2026-11-27T20:00:00-08:00',
                'written_permit_status': 'absent', 'permit_scope_claim': 'unverified',
                'requested_motion': 'moving'}
    variants = {
        'truck_route': ('truck_route_designation', 'truck_route'),
        'non_truck_route': ('truck_route_designation', 'non_truck_route'),
        'weight_below_8000': ('unladen_weight_lb', 7999),
        'weight_8000': ('unladen_weight_lb', 8000),
        'weight_above_8000': ('unladen_weight_lb', 8001),
        'other_district': ('residence_district', 'other'),
        'residence_district': ('residence_district', 'residence'),
        'time_1859': ('civil_clock_time', '2026-11-27T18:59:00-08:00'),
        'time_1901': ('civil_clock_time', '2026-11-27T19:01:00-08:00'),
        'time_0559': ('civil_clock_time', '2026-11-27T05:59:00-08:00'),
        'time_0601': ('civil_clock_time', '2026-11-27T06:01:00-08:00'),
        'permit_absent': ('written_permit_status', 'absent'),
        'permit_written': ('written_permit_status', 'present'),
        'permit_scope_match': ('permit_scope_claim', 'matched'),
        'permit_scope_mismatch': ('permit_scope_claim', 'mismatched'),
        'stationary': ('requested_motion', 'stationary'),
        'moving': ('requested_motion', 'moving')}
    groups = {'truck_route': 'route', 'non_truck_route': 'route',
              'weight_below_8000': 'weight', 'weight_8000': 'weight', 'weight_above_8000': 'weight',
              'other_district': 'district', 'residence_district': 'district',
              'time_1859': 'night_entry', 'time_1901': 'night_entry',
              'time_0559': 'night_exit', 'time_0601': 'night_exit',
              'permit_absent': 'permit_existence', 'permit_written': 'permit_existence',
              'permit_scope_match': 'permit_scope', 'permit_scope_mismatch': 'permit_scope',
              'stationary': 'movement', 'moving': 'movement'}
    descriptions = [case['recording_description'] for case in expected.values()]
    if not descriptions or any(d != descriptions[0] for d in descriptions):
        raise ValueError('All semantic cases must retain one exact capture contract')
    def full(values):
        return {name: {'kind': kind, 'unit': 'lb' if name == 'unladen_weight_lb' else 'category',
                       'value': values[name]} for name, kind, _ in parameters}
    baseline = {'case_id': AID + '__semantic_baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared neutral context only; no delivered recording or legal label.',
                'variable_assignments': full(defaults), 'unresolved_judgment_calls': [],
                'recording_description': descriptions[0]}
    cases = [baseline]
    for case_id in expected:
        suffix = case_id.removeprefix(AID + '__')
        name, value = variants[suffix]
        values = dict(defaults, **{name: value})
        group = groups[suffix]
        probe = {'primary_variable': name, 'comparison_or_standard': 'source-grounded ' + group + ' contrast',
                 'target_value_or_branch': value}
        target_type = 'boundary_probe'
        metadata = {}
        if group == 'weight':
            probe.update(threshold_ref='activation.numeric_conditions[0]', operator='>',
                         unit='lb', test_value=value)
            metadata['epsilon_used'] = 1
        cases.append({'case_id': case_id, 'target_law_id': LAW, 'target_type': target_type,
                      'rationale': expected[case_id]['rationale'], 'variable_assignments': full(values),
                      'unresolved_judgment_calls': [], 'recording_description': expected[case_id]['recording_description'],
                      'paired_probe_id': AID + '__' + group, 'deliberate_differences': [name],
                      'probe': probe, **metadata})
    semantic_cases = {'cell_id': 'C394566', 'actor': ACTOR, 'status': 'draft',
                      'cases': cases, 'sweep_specs': []}
    files = {'relevance_batch': relevance, 'relevance': relevance,
             'template': template, 'bindings': bindings, 'cases': semantic_cases}
    refs_index = {}
    for stage, value in files.items():
        name = 'semantic-cases.json' if stage == 'cases' else stage + '.json'
        path = HERE / 'proposals' / name
        write(path, value)
        refs_index[stage] = {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}
    refs_index['judgment_observables'] = []
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs_index}
    write(HERE / 'proposals/semantic-index.json', index)
    print(json.dumps({'semantic_cases': len(cases), 'delivery_cases': len(cases)-1}))


if __name__ == '__main__':
    main()
