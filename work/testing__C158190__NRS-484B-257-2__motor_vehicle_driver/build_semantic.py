"""Author exact NRS 484B.257(2) canonical, source-gated stage proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law']
IDENT = LAW['id'] + '@' + ASSIGNMENT['actor']
RECORDING = json.loads((ROOT / 'construction.json').read_text())['recording_description']


def write(name, value):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest()}


def judgment(phrase, channels):
    units = {item['name']: item['unit'] for item in RECORDING['channels']}
    needs = [{'name': name, 'unit': units[name],
              'description': 'Original source-bound measurement for ' + phrase}
             for name in channels]
    return {'template_id': IDENT, 'phrase': phrase, 'note': '', 'status': 'draft',
            'observable_requirements': {
                'observables': needs,
                'context_inputs': [{'name': 'reviewed_nonthrough_stop_site_packet',
                                    'unit': 'source record',
                                    'description': 'Reviewed map, controls, routes and obligations'}],
                'sweep_dimensions': [{'name': 'requested_other_station_m', 'unit': 'm',
                                      'description': 'Requested other station, observed independently'}],
                'landmarks': [], 'recording_needs': needs,
                'limitations': ['No legal hazard or cautious-proceeding threshold is supplied.',
                                'Original Native context and full histories are required.']}}


def main():
    quote = LAW['text']
    relevance = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': quote,
                                    'applies_to': [PLAN['actor']],
                                    'relevance_type': 'assigned non-through stop intersection',
                                    'confidence': 'medium',
                                    'notes': 'Actual classification and devices need reviewed Native sources.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    params = [{'name': name, 'kind': kind, 'range_or_domain': domain}
              for name, kind, domain in (
                  ('through_phase', 'world_setup', 'within or approaching at physical ego entry'),
                  ('approach_policy', 'controller', 'stop or uninterrupted request'),
                  ('requested_other_station_m', 'world_setup', '0, 8 or 35 m requested'),
                  ('non_through_highway', 'world_setup', 'source-reviewed true'),
                  ('ego_control', 'world_setup', 'source-reviewed stop sign'),
                  ('officer_controls', 'world_setup', 'source-reviewed absent'),
                  ('signal_controls', 'world_setup', 'source-reviewed absent'))]
    phrases = [
        ('immediate hazard', ('other_body_position', 'other_phase', 'ego_body_position')),
        ('proceed cautiously', ('ego_speed', 'ego_body_position', 'sightlines')),
        ('yielding to vehicles not so obligated to stop or yield',
         ('other_obligation', 'other_body_position', 'across_or_within'))]
    template = {'template_id': IDENT, 'law_id': LAW['id'], 'actor': PLAN['actor'],
                'quote': quote, 'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'Vehicle entering a non-through intersection with a stop or yield entrance and no controlling police officer or traffic-control signal.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Obey the applicable stop/yield sign before entry in subsection 1 manner, proceed cautiously, and yield to non-obligated vehicles within or immediately approaching throughout movement across or within.',
                                   'type': 'must', 'numeric_conditions': []},
                    'exceptions': [{'trigger': 'Traffic controlled by police officer or traffic-control signal',
                                    'effect': 'This subsection yields to that control',
                                    'replacement_obligation': 'Follow controlling officer or signal under its applicable law',
                                    'source_clause': 'Except when traffic is being controlled by a police officer or a traffic-control signal'}],
                    'timing': {'description': 'Before entry for sign obedience, then throughout movement across or within the intersection for yielding.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': ''}
                                              for phrase, _ in phrases]},
                'parameter_refs': params}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = [write('judgment-' + str(i) + '.json',
                                          judgment(phrase, channels))
                                    for i, (phrase, channels) in enumerate(phrases)]
    binding = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
               'established_contexts': ['Reviewed non-through and all-entrance device evidence pending'],
               'law_refs': [{'template_id': IDENT, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**row, 'used_by_laws': [LAW['id']]}
                                       for row in params]}
    refs['bindings'] = write('bindings.json', binding)

    def assignments(values):
        return {p['name']: {'kind': p['kind'], 'value': values[p['name']],
                            'note': 'Requested physical setup/control; original result measured separately'}
                for p in params}

    baseline = PLAN['cases'][0]['draft_variables']
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Neutral sourced context definition; no baseline execution or legal label.',
              'variable_assignments': assignments(baseline),
              'unresolved_judgment_calls': [], 'recording_description': RECORDING}]
    pairs = {'occupied_response': 'occupied_vs_approaching',
             'approaching_near_response': 'approach_station_sweep',
             'approaching_far_response': 'approach_station_sweep',
             'approaching_near_uninterrupted': 'response_vs_uninterrupted'}
    for row in PLAN['cases']:
        suffix = row['case_id'].removeprefix(ROOT.name + '__')
        values = row['draft_variables']
        changed = [name for name in baseline if values[name] != baseline[name]]
        cases.append({'case_id': row['case_id'], 'target_law_id': LAW['id'],
                      'target_type': 'boundary_probe',
                      'rationale': 'Original-frame phase, station and response probe; physical/legal outcome unresolved.',
                      'paired_probe_id': pairs[suffix],
                      'deliberate_differences': changed or ['through_phase'],
                      'probe': {'primary_variable': changed[0] if changed else 'through_phase',
                                'comparison_or_standard': 'same reviewed intersection and independent original measurement',
                                'target_value_or_branch': values[changed[0]] if changed else values['through_phase']},
                      'variable_assignments': assignments(values),
                      'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
                      'recording_description': RECORDING})
    specs = [{'sweep_id': name, 'target_law_id': LAW['id'],
              'judgment_refs': [{'phrase': phrase, 'note': ''}],
              'status': 'incomplete',
              'rationale': 'Feasible original range/spacing require reviewed site geometry, participant trajectories and physical source measurements.',
              'missing_inputs': ['Reviewed original non-through site, routes, response history and realized physical windows']}
             for name, phrase in (('immediate_hazard_source_review', phrases[0][0]),
                                  ('caution_source_review', phrases[1][0]),
                                  ('non_obligated_yield_source_review', phrases[2][0]))]
    refs['cases'] = write('cases.json', {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
        'status': 'draft', 'cases': cases, 'sweep_specs': specs,
        'sweeps_expanded': True, 'semantic_status': 'partial_source_gated_judgment_sweeps'})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name, 'stages': refs,
        'status': 'partial_source_gated_judgment_sweeps'})
    print('canonical source-gated stages and selected cases:', len(cases) - 1)


if __name__ == '__main__':
    main()
