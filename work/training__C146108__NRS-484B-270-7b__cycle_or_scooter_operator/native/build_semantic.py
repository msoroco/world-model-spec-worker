"""Author exact-law semantic stages for selected full-pass cases."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OUT = ROOT / 'proposals'
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': sha(path)}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
    lid = law['id']
    tid = lid + '@' + actor
    exact = ('The operator of a bicycle, an electric bicycle or an electric scooter shall not: '
             'Overtake and pass a motor vehicle unless the operator can do so safely without '
             'endangering himself or herself or the occupants of the motor vehicle.')
    assert law['text'] == exact
    phrases = [
        ('Overtake and pass a motor vehicle',
         'Verify the qualifying rider and motor-vehicle classes and an original behind-to-clear-ahead pass.'),
        ('safely without endangering himself or herself or the occupants of the motor vehicle',
         'Measure the full-body gap, closing motion, passing side and occupant evidence over the whole pass; no numeric legal threshold is supplied.'),
    ]
    relevance = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': lid, 'quote': exact, 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'The one-way multilane overtaking cell is planning context; original rider class, motor vehicle, complete pass and endangerment require source review.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    parameters = [
        {'name': 'rider_class', 'kind': 'world_setup',
         'range_or_domain': ['bicycle', 'electric_bicycle', 'electric_scooter']},
        {'name': 'rider_y_m', 'kind': 'controller',
         'range_or_domain': 'source-checked lateral center within the one-way through lanes'},
        {'name': 'motor_vehicle_context', 'kind': 'world_setup',
         'range_or_domain': 'original motor-vehicle class, full body and occupant evidence'},
    ]
    template = {'template_id': tid, 'law_id': lid, 'actor': actor, 'quote': exact,
        'status': 'draft', 'structure': {'law_id': lid,
            'activation': {'condition': 'qualifying cycle or scooter operator overtakes and passes a motor vehicle',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_not',
                           'description': 'operator must not overtake and pass unless able to do so safely without endangering the operator or motor-vehicle occupants',
                           'source_clause': exact, 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'entire observed pass from behind until clear ahead',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in phrases]},
        'parameter_refs': parameters}
    refs['template'] = write('template.json', template)
    requirements = [
        {'observables': [
            {'name': 'drv.overtaking', 'unit': 'structured event',
             'description': 'Original full-body rider pass from behind to clear ahead.'},
            {'name': 'ru.motor_vehicle', 'unit': 'structured identity',
             'description': 'Original motor-vehicle class and body geometry.'}],
         'context_inputs': [],
         'recording_needs': [
            {'name': 'drv.overtaking', 'unit': 'structured event',
             'description': 'Timestamp-joined rider and motor actor bodies over all frames.'},
            {'name': 'ru.motor_vehicle', 'unit': 'structured identity',
             'description': 'Original vehicle class and synchronized camera views.'}],
         'limitations': ['A generated bicycle carrier does not certify the physical Class 1 electric-bicycle asset.']},
        {'observables': [
            {'name': 'rel.surface_gap', 'unit': 'm',
             'description': 'Minimum full-body surface separation across the complete pass.'},
            {'name': 'drv.time_to_conflict', 'unit': 's',
             'description': 'Pose-derived initial time to rear overlap.'},
            {'name': 'ru.occupant_count', 'unit': 'count',
             'description': 'Original motor-vehicle occupant context.'}],
         'context_inputs': [],
         'recording_needs': [
            {'name': 'rel.surface_gap', 'unit': 'm',
             'description': 'Full-body rider and motor extents with frame join.'},
            {'name': 'drv.time_to_conflict', 'unit': 's',
             'description': 'Original relative motion with timestamp join.'},
            {'name': 'ru.occupant_count', 'unit': 'count',
             'description': 'Sourced occupant review and driver view.'}],
         'limitations': ['Safe pass and endangerment remain legal judgments without a supplied numeric threshold.']},
    ]
    refs['judgment_observables'] = []
    for index, ((phrase, note), req) in enumerate(zip(phrases, requirements), 1):
        value = {'template_id': tid, 'phrase': phrase, 'note': note, 'status': 'draft',
                 'observable_requirements': dict(req, sweep_dimensions=[], landmarks=[])}
        refs['judgment_observables'].append(write(f'judgment-observables-{index}.json', value))
    binding = {'cell_id': cell['cell_id'], 'actor': actor, 'status': 'draft',
        'established_contexts': ['One-way multilane overtaking is a cell target; original classes and pass require review.'],
        'law_refs': [{'template_id': tid, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[lid]) for item in parameters]}
    refs['bindings'] = write('bindings.json', binding)
    cases = json.loads((OUT / 'cases.json').read_text())
    for case in cases['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        values = case['variable_assignments']
        case['variable_assignments'] = {
            'rider_class': {'kind': 'world_setup', 'value': values['rider_class']},
            'rider_y_m': {'kind': 'controller', 'value': values['rider_y_m']},
            'motor_vehicle_context': {'kind': 'world_setup',
                                      'value': 'source-reviewed motor vehicle, body and occupants required'}}
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in phrases]
        family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
        construction = json.loads((ROOT / family / suffix / 'primary/construction.json').read_text())
        case['recording_description'] = construction['recording_description']
        case['target_type'] = 'judgment_sweep'
        case['paired_probe_id'] = 'c146108-electric-bicycle-clearance-pair' if suffix.startswith('electric') else 'c146108-bicycle-alternative'
        case['deliberate_differences'] = ['rider_y_m']
        case['probe'] = {'primary_variable': 'rider_y_m',
                         'comparison_or_standard': 'source-measured full-body pass clearance and unresolved endangerment review',
                         'target_value_or_branch': values['rider_y_m']}
    bicycle = json.loads((ROOT / 'draft-bicycle/bicycle_pass_wide/primary/construction.json').read_text())
    cases['cases'].append({'case_id': AID + '__baseline', 'target_law_id': lid,
        'target_type': 'baseline',
        'rationale': 'Shared planning reference for original motor-vehicle and road context; no delivery capture is selected.',
        'variable_assignments': {
            'rider_class': {'kind': 'world_setup', 'value': 'bicycle'},
            'rider_y_m': {'kind': 'controller', 'value': -1.75},
            'motor_vehicle_context': {'kind': 'world_setup',
                                      'value': 'source-reviewed motor vehicle, body and occupants required'}},
        'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
        'recording_description': bicycle['recording_description']})
    cases['sweep_specs'] = [{'sweep_id': 'full_pass_and_endangerment', 'target_law_id': lid,
        'judgment_refs': template['structure']['judgment_calls_needed'],
        'status': 'incomplete',
        'rationale': 'Full-body pass and relative motion are measured, but the legal safety/endangerment conclusion requires source review.',
        'missing_inputs': ['Original Native rider and motor class and camera visibility',
                           'Independent occupant and legal endangerment judgment']}]
    cases['sweeps_expanded'] = True
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    from batch_pipeline import stages
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    request = {'cell': cell, 'actor': actor}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, deepcopy(relevance), {'request': request,
                        'law_records': {lid: law}, 'dependencies': []})
    stages.validate('template', deepcopy(template), {'request': {'law_id': lid, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    completed = deepcopy(template)
    for phrase, note in phrases:
        observable = json.loads((OUT / ('judgment-observables-' + str(phrases.index((phrase, note)) + 1) + '.json')).read_text())
        stages.validate('judgment_observables', deepcopy(observable),
                        {'request': {'template_id': tid, 'phrase': phrase, 'note': note}, 'dependencies': []})
        next(item for item in completed['structure']['judgment_calls_needed']
             if item['phrase'] == phrase)['observable_requirements'] = observable['observable_requirements']
    stages.validate('bindings', deepcopy(binding), {'request': dict(request, template_ids=[tid]),
                    'canonical_parameter_rules': rules, 'dependencies': [template]})
    stages.validate('cases', deepcopy(cases), {'request': request,
                    'dependencies': [binding], 'templates': [completed],
                    'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    print('semantic stages pass')


if __name__ == '__main__':
    main()
