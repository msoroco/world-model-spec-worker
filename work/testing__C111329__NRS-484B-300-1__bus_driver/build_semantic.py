"""Build exact source-gated canonical semantic stage proposals."""
import hashlib
import json
from pathlib import Path

from package_spec import ACTOR, AID, CASES, CELL, HERE, LAW, RECORDING, ROOT, case_id

STAGES = HERE / 'proposals'
STAGES.mkdir(exist_ok=True)


def put(name, value):
    path = STAGES / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(value):
    return {'kind': 'world_setup', 'value': value, 'unit': 'source request'}


def main():
    frozen = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    quote = frozen['law']['text']
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = put('relevance.json', relevance)
    put('relevance-batch.json', relevance)
    template_id = LAW + '@' + ACTOR
    parameters = [
        {'name': name, 'kind': 'world_setup', 'range_or_domain': domain, 'unit': 'source request'}
        for name, domain in (
            ('device_aspect', 'source-observed red or green instruction'),
            ('bus_control_policy', 'hold red, enter red, follow source-backed officer, proceed green'),
            ('police_direction', 'source-backed proceed or recorded absence'),
            ('line_entry_request', 'controller target only; original entry separately measured'))
    ]
    template = {'template_id': template_id, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'Bus driver approaches an intersection governed by a source-verified official traffic-control device placed in accordance with applicable NRS chapters.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Obey the governing device instruction, subject to the exact statutory 307 exception and contemporaneous police direction.',
                                   'type': 'must', 'numeric_conditions': []},
                    'exceptions': [{'source_clause': 'Except as otherwise provided in NRS 484B.307',
                                    'disposition': 'original source review required'},
                                   {'source_clause': 'unless at the time otherwise directed by a police officer',
                                    'disposition': 'contemporaneous original authority review required'}],
                    'timing': {'description': 'Original device aspect, direction and bus conduct at the governed approach and stop line.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': parameters}
    template_ref = put('template.json', template)
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [dict(parameter, used_by_laws=[LAW])
                                       for parameter in parameters]}
    binding_ref = put('bindings.json', binding)
    baseline = {'case_id': case_id('baseline'), 'target_law_id': None,
                'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Shared reviewed intersection/device/bus route baseline; no original acceptance or legal verdict.',
                'variable_assignments': {
                    'device_aspect': assignment('red'),
                    'bus_control_policy': assignment('hold_red'),
                    'police_direction': assignment(None),
                    'line_entry_request': assignment(False)},
                'unresolved_judgment_calls': [], 'recording_description': RECORDING}
    cases = [baseline]
    for name, aspect, policy, direction, entry in CASES:
        group = 'red_instruction_conduct' if name in ('red_hold', 'red_enter') else (
            'contemporaneous_police_direction' if name == 'red_police_proceed'
            else 'device_instruction')
        cases.append({'case_id': case_id(name), 'target_law_id': LAW,
                      'target_type': ('compliant_attempt' if name == 'red_hold'
                                      else 'violating_attempt' if name == 'red_enter'
                                      else 'boundary_probe'),
                      'status': 'draft', 'rationale': 'Controlled engineering conduct request conditional on reviewed original device, placement, officer and 307 context; no legal result.',
                      'paired_probe_id': group,
                      'deliberate_differences': (['line_entry_request', 'bus_control_policy']
                                                 if name in ('red_hold', 'red_enter')
                                                 else ['police_direction', 'bus_control_policy', 'line_entry_request']
                                                 if name == 'red_police_proceed'
                                                 else ['device_aspect', 'bus_control_policy', 'line_entry_request']),
                      'variable_assignments': {'device_aspect': assignment(aspect),
                                               'bus_control_policy': assignment(policy),
                                               'police_direction': assignment(direction),
                                               'line_entry_request': assignment(entry)},
                      'unresolved_judgment_calls': [], 'recording_description': RECORDING,
                      'probe': {'primary_variable': 'line_entry_request' if name in ('red_hold', 'red_enter')
                                else 'police_direction' if name == 'red_police_proceed' else 'device_aspect',
                                'comparison_or_standard': 'Compare retained original device, bus-front, officer and 307 source; no requested policy proves compliance.',
                                'target_value_or_branch': name}})
    cases_ref = put('cases.json', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                                  'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
                                'assignment_id': AID,
                                'stages': {'relevance_batch': relevance_ref,
                                           'relevance': relevance_ref,
                                           'template': template_ref,
                                           'judgment_observables': [],
                                           'bindings': binding_ref,
                                           'cases': cases_ref},
                                'status': 'source_gated_draft'})
    print('semantic selected cases:', len(CASES))


if __name__ == '__main__':
    main()
