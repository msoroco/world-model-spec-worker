"""Write source-quoted adjacent-vehicle semantic drafts for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-486-351-1'
ACTOR = 'motorcycle_or_moped_operator'
ASSIGNMENT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR
CASES = (('probe_1', False, 'stationary', 'motorcycle', False),
         ('probe_2', True, 'stationary', 'motorcycle', False),
         ('probe_3', True, 'moving', 'motorcycle', False),
         ('probe_4', True, 'stationary', 'moped', False),
         ('probe_5', True, 'stationary', 'motorcycle', True))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    refs = {}
    relevance = {'cell_id': 'C178141', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen paved road lane-split cell; original classification, duty status, and physical lane occupancy need independent review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'motorcycle or moped', 'note': 'Original blueprint and chapter-specific classification need separate review; unavailable NRS 482.0295 and 482.029 references and autocycle applicability remain unresolved.'},
        {'phrase': 'between moving or stationary vehicles occupying adjacent traffic lanes', 'note': 'Measure original subject and two occupant footprints, lane readback and velocity without an invented persistence or overlap cutoff.'},
        {'phrase': 'except a police officer in the performance of his or her duty', 'note': 'Officer identity and performance of duty require separate independent sources; authored roles or synthetic pixels do not establish exception applicability.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft',
        'quote': TEXT,
        'structure': {'activation': {'description': 'Original source-reviewed person operates a chapter-classified motorcycle or moped among two vehicles occupying adjacent traffic lanes.',
            'source_clause': 'drive a motorcycle or moped between moving or stationary vehicles occupying adjacent traffic lanes'},
            'obligation': {'description': 'Review original motorcycle or moped body position relative to sourced adjacent-lane occupants; reserve statutory meaning and legal conclusion.',
                'type': 'must_not', 'source_clause': 'shall not drive a motorcycle or moped between moving or stationary vehicles', 'numeric_conditions': []},
            'exceptions': [{'description': 'Separately review police-officer identity and actual performance of duty.',
                'source_clause': 'except a police officer in the performance of his or her duty'}],
            'timing': {'description': 'Review source-joined body positions and speed over every original frame; no invented persistence threshold.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'between_adjacent_vehicles', 'kind': 'subject_behavior',
            'range_or_domain': 'original subject body and longitudinal overlap relative to lane occupants'},
            {'name': 'surrounding_vehicle_motion', 'kind': 'world_setup',
             'range_or_domain': 'original surrounding vehicle speed histories, stationary or moving'},
            {'name': 'machine_and_duty_context', 'kind': 'world_setup',
             'range_or_domain': 'separate independent classification, officer identity and duty-performance sources'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    observed = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ('ru.motorcycle', 'rel.occupies', 'police_duty_context')), 1):
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original source and review join for ' + name}],
            'limitations': ['Synthetic body and review inputs establish software behavior only; physical realization and legal outcome remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % index),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C178141', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'adjacent_paved_lane_context',
            'value': 'two source-reviewed adjacent lanes and two lane-occupant vehicles',
            'rationale': 'Frozen paved-road lane-split cell; original lane and vehicle occupancy remains for review.'}],
        'variable_parameters': [{'name': 'between_adjacent_vehicles', 'kind': 'subject_behavior',
            'range_or_domain': 'beside or between original lane occupants', 'used_by_laws': [LAW]},
            {'name': 'surrounding_vehicle_motion', 'kind': 'world_setup',
             'range_or_domain': 'stationary or moving', 'used_by_laws': [LAW]},
            {'name': 'machine_and_duty_context', 'kind': 'world_setup',
             'range_or_domain': 'motorcycle/moped candidate and civilian/police-duty candidate', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    desc = json.loads((HERE / 'draft-exact/probe_1/primary/construction.json').read_text())['recording_description']
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Observe adjacent lanes without a selected between-vehicle target.',
        'variable_assignments': {'between_adjacent_vehicles': {'kind': 'subject_behavior', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': desc}]
    for suffix, between, motion, machine, duty in CASES:
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'controlled_attempt', 'paired_probe_id': 'adjacent_vehicle_split',
            'rationale': 'Request original ' + machine + ' body ' + ('between' if between else 'beside') +
                ' ' + motion + ' adjacent-lane occupants; source-review duty context separately.',
            'deliberate_differences': ['between_adjacent_vehicles', 'surrounding_vehicle_motion', 'machine_and_duty_context'],
            'variable_assignments': {'between_adjacent_vehicles': {'kind': 'subject_behavior', 'value': between},
                'surrounding_vehicle_motion': {'kind': 'world_setup', 'value': motion},
                'machine_and_duty_context': {'kind': 'world_setup', 'value': {'machine_candidate': machine, 'police_duty_requested': duty}}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'between_adjacent_vehicles',
                'comparison_or_standard': 'original adjacent-lane occupants, independent classification and duty review',
                'target_value_or_branch': suffix}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C178141', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{'sweep_id': 'adjacent-vehicle-source-review',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Synthetic diagnostics retain source joins while original classification, duty and legal meaning remain open.',
            'missing_inputs': ['Independent original machine classification, lane occupancy and police-duty sources.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
