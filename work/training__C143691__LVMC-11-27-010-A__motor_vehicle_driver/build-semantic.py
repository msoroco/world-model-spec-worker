"""Author source-grounded semantic stages for exact trail cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
PLAN = json.loads((HERE / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
OUT = HERE / 'proposals'
OUT.mkdir(exist_ok=True)


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'high',
                                    'notes': 'Frozen nonmotorized trail/travel/barrier cell; original administrative sources require review.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance_batch.json', relevance)
    write('relevance.json', relevance)
    judgment = [
        ('official trails plan designation', 'Plan status is an administrative source fact, not inferred from OpenDRIVE lane type.'),
        ('dedicated to the City', 'City dedication needs an independent original record.'),
        ('appropriate signs', 'A visible prop does not establish sign wording or legal authority.'),
        ('emergency vehicle', 'Vehicle blueprint/role is insufficient to establish emergency status.'),
        ('maintenance of the right-of-way', 'The particular right-of-way and use must be sourced.'),
        ('designed for and used by a mobility-impaired person',
         'Actor/asset eligibility remains unresolved in the frozen motor_vehicle_driver cell.'),
    ]
    parameters = [
        {'name': 'route_case', 'kind': 'controller', 'range_or_domain': 'outside or within the source corridor'},
        {'name': 'official_designation', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed status, separate from requested value'},
        {'name': 'city_dedication', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed status, separate from requested value'},
        {'name': 'appropriate_posting', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed sign content and pixels'},
        {'name': 'exception_kind', 'kind': 'world_setup', 'range_or_domain': 'none, emergency, right-of-way maintenance; mobility unresolved'},
    ]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'status': 'draft', 'quote': LAW['text'],
        'structure': {
            'law_id': LAW_ID,
            'activation': {'condition': 'Motorized vehicle operates upon or within a right-of-way meeting all three subsection A prerequisites.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Do not operate the motorized vehicle there when subsection A applies.',
                           'type': 'must_not', 'numeric_conditions': []},
            'exceptions': ['emergency vehicle', 'vehicle used in maintenance of this right-of-way',
                           'motorized wheelchair or device designed for and used by a mobility-impaired person'],
            'timing': {'description': 'Occupancy assessed throughout the original recorded interval.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in judgment],
        },
        'parameter_refs': parameters,
    }
    template_ref = write('template.json', template)
    terms = {
        'official trails plan designation': ['st.bicycle_lane_or_path'],
        'dedicated to the City': ['st.bicycle_lane_or_path'],
        'appropriate signs': ['dev.zone_sign', 'dev.regulatory_sign'],
        'emergency vehicle': ['ru.emergency_vehicle'],
        'maintenance of the right-of-way': ['ru.official_vehicle'],
        'designed for and used by a mobility-impaired person': ['ru.pedestrian'],
    }
    judgment_refs = []
    for index, (phrase, note) in enumerate(judgment, 1):
        names = terms[phrase]
        observables = [{'name': name, 'unit': 'structured',
                        'description': 'Independent original source review for ' + name}
                       for name in names]
        judgment_refs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': observables, 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': observables,
                'limitations': ['Synthetic CPU sources and intended setup do not establish this legal context.'],
            },
        }))
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                'established_contexts': [],
                'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{**item, 'used_by_laws': [LAW_ID]}
                                        for item in parameters]}
    bindings_ref = write('bindings.json', bindings)
    proposal_cases = [{
        'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Unselected frozen trail-cell reference; no delivery recording.',
        'variable_assignments': {name: {'kind': item['kind'], 'value': None}
                                 for name, item in ((p['name'], p) for p in parameters)},
        'unresolved_judgment_calls': [phrase for phrase, _ in judgment],
        'recording_description': json.loads((HERE / 'draft-exact' / 'all_present' /
                                             'primary' / 'construction.json').read_text())['recording_description'],
    }]
    for case in PLAN['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / 'draft-exact' / suffix / 'primary' /
                                   'construction.json').read_text())
        request = case['source_context_request']
        assignments = {'route_case': {'kind': 'controller',
                                      'value': 'outside' if suffix == 'outside' else 'within'}}
        for key, value in request.items():
            assignments[key] = {'kind': 'world_setup', 'value': value}
        proposal_cases.append({
            'case_id': case['case_id'], 'target_law_id': LAW_ID,
            'target_type': 'boundary_probe',
            'rationale': case['physical_target'] + '; source facts reviewed independently',
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [phrase for phrase, _ in judgment],
            'paired_probe_id': 'trail-' + suffix,
            'deliberate_differences': [case['comparison_variable']],
            'probe': {'primary_variable': case['comparison_variable'],
                      'comparison_or_standard': 'source-joined occupancy and source-context contrast; no legal verdict',
                      'target_value_or_branch': suffix},
            'recording_description': construction['recording_description'],
        })
    cases_ref = write('cases.json', {
        'status': 'draft', 'assignment_id': HERE.name, 'law_id': LAW_ID,
        'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
        'cases': proposal_cases, 'sweep_specs': [], 'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': judgment_refs,
                   'bindings': bindings_ref, 'cases': cases_ref}})
    print(json.dumps({'selected_cases': len(proposal_cases) - 1,
                      'judgment_observables': len(judgment_refs)}))


if __name__ == '__main__':
    main()
