"""Author source-gated canonical stage proposals for the exact yield branch."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law']
RECORDING = json.loads((ROOT / 'construction.json').read_text())['recording_description']
TEMPLATE_ID = LAW['id'] + '@' + ASSIGNMENT['actor']
PHRASES = (
    ('has a view of approaching traffic',
     ('nearest_view_stations', 'through_vehicle_motion')),
    ('immediate hazard',
     ('through_vehicle_motion', 'ego_motion_and_crossing')),
    ('yield the right-of-way',
     ('ego_motion_and_crossing', 'through_vehicle_motion')),
)
PARAMETERS = (
    ('approach_policy', 'controller', 'slow or stop at the reviewed nearest-view reference'),
    ('through_state', 'world_setup', 'source-reviewed close or clear approach'),
    ('officer_controls', 'world_setup', 'source-reviewed true or false'),
    ('yield_sign_present', 'world_setup', 'reviewed true'),
    ('stop_line_present', 'world_setup', 'reviewed false'),
    ('near_crosswalk_present', 'world_setup', 'reviewed false'),
    ('signal_controls', 'world_setup', 'source-reviewed false'),
)


def write(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(raw).hexdigest()}


def judgment(phrase, channels):
    units = {item['name']: item['unit'] for item in RECORDING['channels']}
    needs = [{'name': name, 'unit': units[name],
              'description': 'Original frame and source-bound measurement for ' + phrase}
             for name in channels]
    return {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': '',
            'status': 'draft', 'observable_requirements': {
                'observables': needs,
                'context_inputs': [{'name': 'reviewed_yield_site_source',
                                    'unit': 'source',
                                    'description': 'Reviewed sign, reference hierarchy, route, sight and controls'}],
                'sweep_dimensions': [{'name': 'ego_motion_and_crossing', 'unit': 'structured',
                                      'description': 'Measured original approach minimum, not a legal cutoff'},
                                     {'name': 'through_vehicle_motion', 'unit': 'structured',
                                      'description': 'Measured through center at observed all-at-reference event'}],
                'landmarks': [], 'recording_needs': needs,
                'limitations': ['No statutory numeric threshold for view, hazard or yielding is supplied.',
                                'Original reviewed site and Native motion are required.']}}


def assignments(values):
    return {name: {'kind': kind, 'value': values[name],
                   'note': 'Requested setup/control only; original outcome measured separately'}
            for name, kind, _ in PARAMETERS}


def main():
    quote = LAW['text']
    relevance = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW['id'], 'quote': quote,
                     'applies_to': [PLAN['actor']],
                     'relevance_type': 'assigned yield sign with no line/crosswalk and nearest view',
                     'confidence': 'medium',
                     'notes': 'Reviewed actual site, sign, through highway and officer control remain pending.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    params = [{'name': name, 'kind': kind, 'range_or_domain': domain}
              for name, kind, domain in PARAMETERS]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW['id'],
                'actor': PLAN['actor'], 'quote': quote,
                'parameter_refs': params,
                'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'Proper yield sign governs the approach; neither marked stop line nor near crosswalk exists, and officer/signal control does not supersede the sign.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must',
                                   'description': 'Slow or stop for the yield sign at the nearest point with a view, then yield to through-highway vehicles already within or immediately approaching during ego movement across or within.',
                                   'numeric_conditions': []},
                    'exceptions': [{'trigger': 'Traffic controlled by a police officer or traffic-control signal',
                                    'effect': 'This subsection yields to the governing control',
                                    'replacement_obligation': 'Follow the controlling officer or signal under its applicable law',
                                    'source_clause': 'Except when traffic is being controlled by a police officer or a traffic-control signal'}],
                    'timing': {'description': 'Sign response before the reviewed nearest-view reference and yielding throughout the movement across or within the intersection.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': ''}
                                              for phrase, _ in PHRASES]}}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = [write('judgment-' + str(i) + '.json',
                                          judgment(phrase, channels))
                                    for i, (phrase, channels) in enumerate(PHRASES)]
    binding = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
               'status': 'draft',
               'established_contexts': ['Reviewed original site and governing control pending'],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**row, 'used_by_laws': [LAW['id']]}
                                       for row in params]}
    refs['bindings'] = write('bindings.json', binding)
    first = PLAN['cases'][0]
    baseline = {'approach_policy': first['requested_yield_action'],
                'through_state': 'approaching_close' if first['requested_close_through_vehicle'] else 'approaching_clear',
                'officer_controls': False,
                'yield_sign_present': True, 'stop_line_present': False,
                'near_crosswalk_present': False, 'signal_controls': False}
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Neutral sourced context only; no baseline recording or legal label.',
              'variable_assignments': assignments(baseline),
              'unresolved_judgment_calls': [],
              'recording_description': RECORDING}]
    pairs = {'yield_slow_hazard': 'slow_vs_stop',
             'yield_stop_hazard': 'slow_vs_stop',
             'yield_slow_no_hazard': 'through_hazard'}
    for row in PLAN['cases']:
        suffix = row['case_id'].removeprefix(ROOT.name + '__')
        values = dict(baseline, approach_policy=row['requested_yield_action'],
                      through_state='approaching_close' if row['requested_close_through_vehicle'] else 'approaching_clear',
                      officer_controls=False)
        changed = [name for name in baseline if values[name] != baseline[name]]
        primary = changed[0] if changed else 'approach_policy'
        cases.append({'case_id': row['case_id'], 'target_law_id': LAW['id'],
                      'target_type': 'boundary_probe',
                      'rationale': 'Exact yield, reference, phase and exception probe; original physical and legal outcomes unresolved.',
                      'paired_probe_id': pairs[suffix],
                      'deliberate_differences': changed or ['approach_policy'],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'same reviewed intersection and independent original measurement',
                                'target_value_or_branch': values[primary]},
                      'variable_assignments': assignments(values),
                      'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES],
                      'recording_description': RECORDING})
    specs = []
    for name, phrase in (('view_source_review', PHRASES[0][0]),
                         ('immediate_hazard_source_review', PHRASES[1][0]),
                         ('right_of_way_source_review', PHRASES[2][0])):
        specs.append({'sweep_id': name, 'target_law_id': LAW['id'],
                      'judgment_refs': [{'phrase': phrase, 'note': ''}],
                      'status': 'incomplete',
                      'rationale': 'Frozen training bounds are engineering coverage targets, not legal cutoffs or original measurements.',
                      'missing_inputs': ['Reviewed original nearest-view site and source-sealed 900-frame Native attempts']})
    refs['cases'] = write('cases.json', {
        'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
        'cases': cases, 'sweep_specs': specs, 'sweeps_expanded': True,
        'semantic_status': 'partial_source_gated_judgment_sweeps'})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': ROOT.name, 'stages': refs,
                                  'status': 'partial_source_gated_judgment_sweeps'})
    print('source-gated semantic cases:', len(cases) - 1)


if __name__ == '__main__':
    main()
