"""Write canonical source-gated semantic stages for NRS 484B.620(2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'


def write(name, data):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    law = assignment['law']
    recording = json.loads((ROOT / 'construction.json').read_text())['recording_description']
    template_id = law['id'] + '@' + assignment['actor']
    relevance = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': law['id'], 'quote': law['text'],
                                    'applies_to': [plan['actor']],
                                    'relevance_type': 'assigned established speed zone and sign',
                                    'confidence': 'medium',
                                    'notes': 'Zone establishment and sign appropriateness require reviewed sources.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    params = [{'name': name, 'kind': kind, 'range_or_domain': domain}
              for name, kind, domain in (
                  ('direction', 'world_setup', 'eastbound or westbound reviewed lane'),
                  ('requested_mph', 'controller', '20, 24.5 or 30 mph engineering request'),
                  ('zone_mode', 'world_setup', 'established signed, outside, or sign absent'),
                  ('authorized_speed_mph', 'world_setup', '25 mph authored site instruction'))]
    phrase = 'appropriate signs'
    template = {'template_id': template_id, 'law_id': law['id'], 'actor': plan['actor'],
                'quote': law['text'], 'structure': {
                    'law_id': law['id'],
                    'activation': {'condition': 'Speed zone established and appropriate governing speed signs installed on the road.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'A person driving a motor vehicle on the road and in that speed zone may not exceed its authorized speed.',
                                   'type': 'must_not', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'While the motor vehicle is upon the road and in the established speed zone after sign installation.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': ''}]},
                'parameter_refs': params}
    refs['template'] = write('template.json', template)
    need = [{'name': name, 'unit': unit,
             'description': 'Original source-bound evidence for the governing sign'}
            for name, unit in (('sign_installed', 'boolean'),
                               ('authorized_speed_mph', 'mph'),
                               ('inside_zone', 'boolean'))]
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': '', 'status': 'draft',
                'observable_requirements': {
                    'observables': need,
                    'context_inputs': [{'name': 'reviewed_speed_site_packet',
                                        'unit': 'source record',
                                        'description': 'Original zone order, signs, boundaries and direction'}],
                    'sweep_dimensions': [{'name': 'direction', 'unit': 'category',
                                          'description': 'Both reviewed travel directions'}],
                    'landmarks': [], 'recording_needs': need,
                    'limitations': ['No general numerical sign-appropriateness criterion is supplied.',
                                    'Original source and full speed histories are required.']}}
    refs['judgment_observables'] = [write('judgment-0.json', judgment)]
    binding = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
               'established_contexts': ['Narrow road, reviewed speed-zone order and governing signs pending'],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**param, 'used_by_laws': [law['id']]}
                                       for param in params]}
    refs['bindings'] = write('bindings.json', binding)

    def assignments(values):
        return {param['name']: {'kind': param['kind'], 'value': values[param['name']],
                'note': 'Requested physical setup; original result measured separately'}
                for param in params}

    baseline = plan['cases'][0]['draft_variables']
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Neutral source context; no baseline capture or legal label.',
              'variable_assignments': assignments(baseline),
              'unresolved_judgment_calls': [], 'recording_description': recording}]
    pairs = {'signed_below': 'speed_below_above', 'signed_near': 'speed_near_above',
             'signed_above': 'speed_below_above', 'outside_zone': 'zone_occupancy',
             'sign_not_installed': 'sign_installation', 'westbound_signed': 'directional_sign'}
    for row in plan['cases']:
        suffix = row['case_id'].removeprefix(ROOT.name + '__')
        values = row['draft_variables']
        changed = [name for name in baseline if values[name] != baseline[name]]
        primary = changed[0] if changed else 'requested_mph'
        cases.append({'case_id': row['case_id'], 'target_law_id': law['id'],
                      'target_type': 'boundary_probe',
                      'rationale': 'Original speed, occupancy, direction and sign-source comparison; no legal outcome preassigned.',
                      'paired_probe_id': pairs[suffix],
                      'deliberate_differences': changed or ['requested_mph'],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'same reviewed road and independent original measurement',
                                'target_value_or_branch': values[primary]},
                      'variable_assignments': assignments(values),
                      'unresolved_judgment_calls': [phrase],
                      'recording_description': recording})
    specs = [{'sweep_id': 'appropriate_sign_source_review', 'target_law_id': law['id'],
              'judgment_refs': [{'phrase': phrase, 'note': ''}], 'status': 'incomplete',
              'rationale': 'Appropriateness needs reviewed establishment order, actual installed signs and direction.',
              'missing_inputs': ['Reviewed original speed-zone site and sign sources']}]
    refs['cases'] = write('cases.json', {'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'status': 'draft', 'cases': cases, 'sweep_specs': specs,
        'sweeps_expanded': True, 'semantic_status': 'partial_source_gated_sign_review'})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name, 'stages': refs,
        'status': 'partial_source_gated_sign_review'})
    print('canonical source-gated semantic cases:', len(cases) - 1)


if __name__ == '__main__':
    main()
