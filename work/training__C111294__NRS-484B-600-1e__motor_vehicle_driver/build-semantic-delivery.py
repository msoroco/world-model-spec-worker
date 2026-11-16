"""Build source-exact, provisional speed-boundary semantic proposals."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from worker_exchange.semantic_delivery import validate as validate_delivery


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'proposals' / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def build():
    assignment = read(ROOT / 'inputs' / HERE.name / 'assignment.json')
    law = assignment['law']
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    request = {'cell': assignment['cell'], 'actor': actor}
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    draft = read(HERE / 'draft-execution-manifest.json')
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Exact frozen 80 mph clause; original vehicle, speed and Nevada road context remain unverified.'}],
                 'borderline_excluded': []}
    refs = {}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, relevance, deepcopy(common))
        refs[stage] = write(stage, relevance)

    phrase = 'a rate of speed greater than 80 miles per hour'
    note = ('Derive peak speed from original Native velocity and preserve the measurement '
            'interval; an exact-80 diagnostic cannot establish a legal relation.')
    template_id = law_id + '@' + actor
    parameters = [
        ('road_and_territory_context', 'world_setup', 'authored Nevada road context; original Native readback pending'),
        ('subject_vehicle_context', 'world_setup', 'vehicle kind and operator; original Native actor readback pending'),
        ('requested_speed_mph', 'controller', '75, 79.5, 80 and 85 mph engineering requests; not observed speed'),
        ('native_velocity_history', 'subject_behavior', 'original three-axis velocity at 20 Hz for all 480 frames'),
        ('camera_policy', 'controller', 'four synchronized original source cameras')]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': law['text'],
                'structure': {
                    'activation': {'condition': 'person drives or operates a vehicle of any kind or character',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'drive or operate at a speed greater than 80 miles per hour in any event',
                                   'source_clause': law['text'].split(':', 1)[-1].strip(),
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'at any observed instant while driving or operating',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = write('template', template)

    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
                'status': 'draft', 'observable_requirements': {
                    'observables': [
                        {'name': 'kin.velocity', 'unit': 'metres/second',
                         'description': 'Original Native three-axis velocity and frame identity.'},
                        {'name': 'kin.speed', 'unit': 'miles/hour',
                         'description': 'Peak speed computed from original velocity with declared uncertainty.'},
                        {'name': 'ru.subject', 'unit': 'structured',
                         'description': 'Original actor identity and vehicle operation.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [
                        {'name': 'ego_speed', 'unit': 'metres/second',
                         'description': 'All 480 original Native velocity samples.'},
                        {'name': 'ego_pose', 'unit': 'Native x,y,z metres',
                         'description': 'Original actor position and frame identity.'},
                        {'name': 'observed_speed', 'unit': 'miles/hour',
                         'description': 'Derived original speed with declared uncertainty.'}],
                    'limitations': [
                        'Requested speed is not observed speed.',
                        'Synthetic source velocity is only a CPU diagnostic.',
                        'The 80 mph probe remains unresolved within the stated ±0.2 mph interval.']}}
    stages.validate('judgment_observables', judgment,
                    {'request': {'template_id': template_id, 'phrase': phrase, 'note': note},
                     'dependencies': []})
    refs['judgment_observables'] = [write('judgment_observables_speed', judgment)]

    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'absolute_speed_boundary',
                                         'source': 'frozen 80 mph clause and four authored boundary requests; original velocity unverified'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain, 'used_by_laws': [law_id]}
                                       for name, kind, domain in parameters]}
    stages.validate('bindings', binding,
                    {'request': dict(request, template_ids=[template_id]),
                     'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)

    selected = []
    for entry in draft['cases']:
        construction = read(HERE / entry['construction'])
        requested = next(case['requested_setting'] for case in read(HERE / 'case-plan.json')['cases']
                         if case['case_id'] == entry['case_id'])
        assignments = {
            'road_and_territory_context': {'kind': 'world_setup',
                                           'value': 'authored road; original Nevada road and Native designation pending'},
            'subject_vehicle_context': {'kind': 'world_setup',
                                         'value': 'authored motor vehicle; original actor identity pending'},
            'requested_speed_mph': {'kind': 'controller', 'value': requested},
            'native_velocity_history': {'kind': 'subject_behavior', 'value': None},
            'camera_policy': {'kind': 'controller', 'value': 'four_view_nominal'}}
        selected.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                         'target_type': 'boundary_probe',
                         'rationale': 'Four fixed-context requests bracket the strict greater-than-80 clause; observed speed and legal status remain unverified.',
                         'variable_assignments': assignments,
                         'recording_description': construction['recording_description'],
                         'unresolved_judgment_calls': [phrase],
                         'paired_probe_id': 'absolute_speed_boundary',
                         'deliberate_differences': ['requested_speed_mph'],
                         'probe': {'primary_variable': 'requested_speed_mph',
                                   'comparison_or_standard': 'original Native observed peak velocity versus strict 80 mph boundary',
                                   'target_value_or_branch': requested}})
    baseline = deepcopy(selected[0])
    baseline.update(case_id=HERE.name + '__baseline', target_law_id=None,
                    target_type='baseline', rationale='Shared road, actor and capture setup; no baseline recording selected.',
                    unresolved_judgment_calls=[])
    for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(key)
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'cases': [baseline, *selected],
             'sweep_specs': [{'sweep_id': 'observed_speed_boundary', 'target_law_id': law_id,
                              'judgment_refs': [{'phrase': phrase, 'note': note}],
                              'status': 'incomplete',
                              'rationale': 'The four engineering speed requests are selected; an original Native velocity and measurement-interval sweep requires physical capture.',
                              'missing_inputs': ['Original 480-frame Native velocity and actor identity',
                                                 'Original uncertainty-qualified speed relation, especially exact 80 mph']}]}
    augmented = deepcopy(template)
    augmented['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(cases, templates=[augmented], bindings=binding)
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
                    'templates': [augmented], 'canonical_parameter_rules': rules,
                    'judgment_completion_policy': {}})
    refs['cases'] = write('cases', cases)
    refs_path = write('semantic-index',
                      {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
                       'stages': refs})
    proof = validate_delivery(HERE, assignment, draft)
    proof_path = write('semantic-delivery-proof',
                       {'format': 'c111294-semantic-cpu-v1',
                        'stage_validation': proof, 'original_velocity_verified': False,
                        'exact_80_legally_resolved': False})
    return {'stage_validation': proof, 'index': refs_path, 'proof': proof_path,
            'canonical_selected_case_ids': [row['case_id'] for row in selected],
            'selected_delivery_manifest_bound': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
