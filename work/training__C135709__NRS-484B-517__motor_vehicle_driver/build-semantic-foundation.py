"""Validate source-backed draft stages for the assigned taxicab-stand branch."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = ROOT / 'proposals' / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def main():
    source = REPO / 'inputs' / ROOT.name / 'assignment.json'
    assignment = json.loads(source.read_text())
    law = assignment['law']
    law_id, cell_id, actor = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
    request = {'cell': assignment['cell'], 'actor': actor}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
            'applies_to': [actor], 'relevance_type': 'specific_match',
            'confidence': 'medium',
            'notes': 'The assigned curb parking cell permits a taxicab-stand comparison; official designation and signing need original verification.'}],
        'borderline_excluded': []}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, relevance, common)
    refs = {'relevance_batch': write('relevance_batch', relevance),
            'relevance': write('relevance', relevance)}
    template_id = law_id + '@' + actor
    judgments = [
        {'phrase': 'appropriately signed', 'note': 'Activation depends on the actual sign and its applicability.'},
        {'phrase': 'expeditiously loading or unloading of passengers',
         'note': 'The passenger exception needs activity and duration evidence; no numeric legal cutoff is supplied.'},
        {'phrase': 'does not interfere with any bus or taxicab waiting to enter or about to enter such zone',
         'note': 'The passenger exception depends on nearby transit approach and interaction.'},
    ]
    parameters = [
        {'name': 'stand_designation', 'kind': 'world_setup', 'range_or_domain': 'source-verified official designation'},
        {'name': 'stand_sign', 'kind': 'world_setup', 'range_or_domain': 'source-verified sign and applicability'},
        {'name': 'ego_trajectory', 'kind': 'subject_behavior', 'range_or_domain': 'original body and pose history'},
        {'name': 'ego_speed', 'kind': 'subject_behavior', 'range_or_domain': 'original scalar speed history'},
        {'name': 'passenger_loading_activity', 'kind': 'subject_behavior', 'range_or_domain': 'observed passenger activity and timing'},
        {'name': 'taxicab_approach', 'kind': 'world_setup', 'range_or_domain': 'observed waiting or approaching taxicab'},
        {'name': 'commanded_stand_occupancy', 'kind': 'controller', 'range_or_domain': 'predeclared stand entry or bypass'},
        {'name': 'commanded_approach_speed', 'kind': 'controller', 'range_or_domain': 'predeclared m/s target'},
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': law['text'],
        'structure': {'activation': {'context': 'officially designated and appropriately signed taxicab stand',
                                      'subject': 'operator of a vehicle other than a taxicab'},
            'obligation': {'type': 'must_not', 'action': 'stop, stand or park in that taxicab stand',
                'source_clause': 'or a taxicab in a taxicab stand'},
            'exceptions': [{'name': 'passenger_loading',
                'source_clause': 'except that the driver of a passenger vehicle may temporarily stop there and for the purpose of and while actually engaged in expeditiously loading or unloading of passengers when such stopping does not interfere with any bus or taxicab waiting to enter or about to enter such zone',
                'replacement_obligation': 'none stated'}],
            'timing': {'description': 'while the subject vehicle occupies the signed stand', 'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': parameters}
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
        'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = write('template', template)
    refs['judgment_observables'] = []
    for index, judgment in enumerate(judgments):
        observable = {'template_id': template_id, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {'observables': [
                {'name': 'ego_pose', 'unit': 'structured', 'description': 'Original frame-joined vehicle body history.'},
                {'name': 'ego_speed', 'unit': 'm/s', 'description': 'Original frame-joined subject speed.'}],
                'context_inputs': [{'name': 'stand_readback', 'unit': 'structured',
                    'description': 'Generated Native stand geometry and source-reviewed designation and sign.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'four_source_views', 'unit': 'video',
                    'description': 'Synchronized stand, approach and subject views.'}],
                'limitations': ['Authored signs and synthetic observations do not establish official designation, lawful signing, passenger purpose or noninterference.']}}
        stages.validate('judgment_observables', observable,
            {'request': {'template_id': template_id, **judgment}, 'dependencies': []})
        refs['judgment_observables'].append(write('judgment_observables_' + str(index), observable))
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(parameter, used_by_laws=[law_id]) for parameter in parameters]}
    stages.validate('bindings', binding, {'request': dict(request, template_ids=[template_id]),
        'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)
    description = {'channels': [
        {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
         'method': 'retained original Native actor/frame and source-camera join',
         'time_window': '240 frames', 'reference_frame': 'authored OpenDRIVE coordinates',
         'uncertainty': '50 ms frame bracket; physical stand and activity unverified'}
        for name, unit in (('ego_pose', 'structured'), ('ego_speed', 'm/s'),
                           ('taxicab_stand_occupancy_by_nontaxicab', 'bool'),
                           ('four_source_views', 'video'))],
        'context_inputs': [{'name': 'stand_readback', 'unit': 'structured',
            'method': 'source-hashed generated Native map and human sign review'}],
        'limitations': ['Official designation, appropriate signing, actual parking, passenger activity and noninterference require original review.']}
    def assignments(occupied):
        values = {'stand_designation': 'source verification pending',
                  'stand_sign': 'authored sign, physical verification pending',
                  'taxicab_approach': 'no waiting taxicab requested',
                  'commanded_stand_occupancy': occupied,
                  'commanded_approach_speed': 8.0}
        return {row['name']: {'kind': row['kind'],
                             'value': None if row['kind'] == 'subject_behavior' else values[row['name']],
                             'unit': 'm/s' if row['name'] in ('ego_speed', 'commanded_approach_speed')
                             else 'bool' if row['name'] == 'commanded_stand_occupancy'
                             else 'structured'} for row in parameters}
    baseline = {'case_id': ROOT.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Neutral authored road context; no original is claimed.',
        'variable_assignments': assignments(False), 'unresolved_judgment_calls': [],
        'recording_description': description}
    selected = []
    for witness, occupied in (('reference', False), ('contrast', True)):
        selected.append({'case_id': ROOT.name + '__' + witness,
            'target_law_id': law_id, 'target_type': 'boundary_probe',
            'rationale': 'Controlled authored stand-occupancy comparison; physical and legal outcome unresolved.',
            'paired_probe_id': ROOT.name + '__comparison_main',
            'deliberate_differences': ['commanded_stand_occupancy'],
            'probe': {'primary_variable': 'commanded_stand_occupancy',
                      'comparison_or_standard': 'signed stand occupancy request',
                      'target_value_or_branch': witness},
            'variable_assignments': assignments(occupied),
            'unresolved_judgment_calls': [item['phrase'] for item in judgments],
            'recording_description': description})
    sweep = {'sweep_id': 'stand_activation_and_passenger_exception_review',
        'target_law_id': law_id,
        'judgment_refs': [dict(item, observable_requirements=json.loads(
            (ROOT / refs['judgment_observables'][index]['path']).read_text())['observable_requirements'])
            for index, item in enumerate(judgments)],
        'status': 'incomplete',
        'rationale': 'Original designation, signing, loading activity and interference observations need independent review before a qualitative sweep can be fixed.',
        'missing_inputs': ['Original generated Native stand and sign readback',
            'Reviewed passenger loading and nearby taxicab approach']}
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'sweep_specs': [sweep], 'sweeps_expanded': True,
        'cases': [baseline, *selected]}
    template_with_observables = json.loads(json.dumps(template))
    for index, item in enumerate(template_with_observables['structure']['judgment_calls_needed']):
        item['observable_requirements'] = sweep['judgment_refs'][index]['observable_requirements']
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
        'templates': [template_with_observables], 'canonical_parameter_rules': rules,
        'judgment_completion_policy': {}})
    refs['cases'] = write('cases', cases)
    write('semantic-index', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name, 'stages': refs, 'status': 'draft',
        'original_native_observed': False})
    proof = {'format': 'c135709-semantic-foundation-v1', 'assignment_id': ROOT.name,
        'assignment_sha256': sha(source), 'references': refs,
        'stages_validated': ['relevance_batch', 'relevance', 'template',
                             'judgment_observables', 'bindings', 'cases'],
        'cases_stage_validated': True, 'original_native_observed': False,
        'legal_verdict': None}
    write('semantic-foundation-proof', proof)
    print(json.dumps({'stages': 8, 'proof_sha256': sha(ROOT / 'proposals/semantic-foundation-proof.json')}))


if __name__ == '__main__':
    main()
