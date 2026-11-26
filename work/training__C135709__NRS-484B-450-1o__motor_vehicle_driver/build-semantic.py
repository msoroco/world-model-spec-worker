"""Write source-quoted device-zone semantic stages for independent local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-450-1o'
ACTOR = 'motor_vehicle_driver'
ASSIGNMENT = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    desc = json.loads((HERE / 'draft-exact/false/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen narrow-road parking cell; official device status and legal outcome require independent source review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write(HERE / 'proposals/relevance-batch.json', relevance)
    refs['relevance'] = write(HERE / 'proposals/relevance.json', relevance)
    judgments = [
        {'phrase': 'official traffic-control devices', 'note': 'Device identity, placement authority, traffic purpose and legal consistency require separate original sources; authored pixels alone do not establish official status.'},
        {'phrase': 'stop, stand or park', 'note': 'Original rest and footprint are measured; responsible person, covered vehicle, purpose and actual service activity need independent source review.'},
        {'phrase': 'except when necessary to avoid conflict with other traffic', 'note': 'Traffic context and necessity, other-law compliance, police direction and device direction require separate source review; no legal conclusion follows from synthetic absence.'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft',
        'quote': TEXT,
        'structure': {'activation': {'description': 'A source-reviewed official traffic-control device governs the stopping place and its exact prohibition is effective for this person and vehicle.',
            'source_clause': 'At any place where official traffic-control devices prohibit stopping, standing or parking.'},
            'obligation': {'description': 'Observe the original subject stop, stand or park route and full body position at the governed place, reserving legal classification.',
                'type': 'must_not', 'source_clause': 'A person shall not stop, stand or park a vehicle', 'numeric_conditions': []},
            'exceptions': [{'description': 'Source-review necessity to avoid traffic conflict.', 'source_clause': 'except when necessary to avoid conflict with other traffic'},
                {'description': 'Source-review compliance with other applicable law.', 'source_clause': 'in compliance with law'},
                {'description': 'Source-review directions of a police officer or official traffic-control device.', 'source_clause': 'the directions of a police officer or official traffic-control device'}],
            'timing': {'description': 'Review device conditions and civil time over every original stationary frame; no invented duration cutoff.'},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': 'device_zone_overlap', 'kind': 'subject_behavior',
            'range_or_domain': 'original Native body footprint relative to independently reviewed device-governed extent'},
            {'name': 'official_device_status', 'kind': 'world_setup',
             'range_or_domain': 'independent authority, placement and legal consistency review'},
            {'name': 'exception_context', 'kind': 'world_setup',
             'range_or_domain': 'separate traffic conflict, other law, police and device direction sources'}]}
    refs['template'] = write(HERE / 'proposals/template.json', template)
    observed = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ('device_authority', 'vehicle_activity', 'traffic_conflict_context')), 1):
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original source-joined observation of ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original source and review join for ' + name}],
            'limitations': ['Synthetic pixels and source-shaped reviews establish software behavior only; official status and legal outcome remain open.']}
        observed.append(write(HERE / ('proposals/judgment-%d.json' % index),
            {'template_id': TEMPLATE, 'phrase': judgment['phrase'], 'note': judgment['note'],
             'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [{'name': 'device_and_narrow_road_context',
            'value': 'authored NO_PARKING device on narrow road with independently reviewed status',
            'rationale': 'Frozen catalog cell; original device authority and instructions remain for review.'}],
        'variable_parameters': [{'name': 'device_zone_overlap', 'kind': 'subject_behavior',
            'range_or_domain': 'outside or inside source-reviewed governed zone', 'used_by_laws': [LAW]},
            {'name': 'target_station_inside_zone', 'kind': 'controller',
             'range_or_domain': 'outside or inside station request', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write(HERE / 'proposals/bindings.json', binding)
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Observe narrow-road and device context without targeting stationary occupancy.',
        'variable_assignments': {'device_zone_overlap': {'kind': 'subject_behavior', 'value': None},
            'target_station_inside_zone': {'kind': 'controller', 'value': None}},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments], 'recording_description': desc}]
    for suffix, inside in (('false', False), ('true', True)):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'paired_probe_id': 'device_zone_station',
            'rationale': 'Request stationary ' + ('inside' if inside else 'outside') +
                ' the device zone; measure original body overlap without legal label.',
            'deliberate_differences': ['target_station_inside_zone'],
            'variable_assignments': {'device_zone_overlap': {'kind': 'subject_behavior', 'value': None},
                'target_station_inside_zone': {'kind': 'controller', 'value': inside}},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'device_zone_overlap',
                'comparison_or_standard': 'source-reviewed official device and governed extent',
                'target_value_or_branch': 'inside' if inside else 'outside'}})
    refs['cases'] = write(HERE / 'proposals/cases.json', {'cell_id': 'C135709', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{'sweep_id': 'device-zone-parking-review',
            'target_law_id': LAW, 'judgment_refs': judgments, 'status': 'incomplete',
            'rationale': 'Synthetic diagnostics preserve source joins while device authority, legal consistency and exceptions remain open.',
            'missing_inputs': ['Independent original device, condition, activity and exception sources.']}],
        'sweeps_expanded': True, 'cases': cases})
    write(HERE / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
