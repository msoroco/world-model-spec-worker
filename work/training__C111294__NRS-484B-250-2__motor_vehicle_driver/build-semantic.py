"""Build exact-law draft semantic stages for the selected C111294 pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROPOSALS = HERE / 'proposals'
LAW = 'NRS-484B-250-2'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'approximately the same time'
NOTE = 'Entry-time relation requires a source-reviewed legal judgment; no numeric cutoff is supplied.'
TERMS = ('st.intersection', 'st.lane_enters', 'drv.entering_intersection',
         'drv.arrival_order', 'rel.bearing', 'drv.yields_to',
         'dev.traffic_signal', 'drv.turning')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': 'proposals/' + name, 'sha256': sha(path)}


def assignment(kind, value):
    return {'kind': kind, 'value': value}


def variables(wait, other_present=True):
    return {
        'ego_yield_wait_s': assignment('controller', wait),
        'commanded_approach_speed_mps': assignment('controller', 5.0),
        'ego_speed': assignment('subject_behavior', None),
        'authored_other_vehicle_present': assignment('world_setup', other_present),
        'authored_intersection_control': assignment('world_setup', 'no_authored_devices'),
    }


def build():
    frozen = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    law_text = frozen['law']['text']
    recording = json.loads((HERE / 'selected-v5/controlled_1/primary/construction.json').read_text())['recording_description']
    relevance = {'cell_id': 'C111294', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW,
            'quote': 'When two vehicles enter an intersection from different highways at approximately the same time',
            'applies_to': [ACTOR], 'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'The frozen intersection/travel/other-vehicle cell can exercise the exact two-highway entry clause; applicability qualifiers remain source-reviewed unknowns.'}],
        'borderline_excluded': []}
    if relevance['relevant_laws'][0]['quote'] not in law_text:
        raise ValueError('Frozen exact quote changed')
    relevance_ref = write('relevance.json', relevance)
    batch_ref = write('relevance-batch.json', relevance)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': law_text,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'Two vehicles enter the intersection from different highways at approximately the same time, with the subject vehicle on the left.',
                           'numeric_conditions': []},
            'obligation': {'description': 'The left-side driver shall yield right-of-way to the vehicle on the right when the clause applies.',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [
                {'trigger': 'subsection 4 otherwise provides', 'effect': 'Dependent source rule must be reviewed',
                 'replacement_obligation': 'unresolved',
                 'source_clause': 'Except as otherwise provided in subsection 4 [NRS-484B-250-4]'},
                {'trigger': 'official traffic-control devices control the intersection',
                 'effect': 'This section does not apply under the quoted condition',
                 'replacement_obligation': 'unresolved',
                 'source_clause': 'this section does not apply at intersections controlled by official traffic-control devices'},
                {'trigger': 'opposite-direction approaches with one intending or making a left turn',
                 'effect': 'This section does not apply under the quoted condition',
                 'replacement_obligation': 'unresolved',
                 'source_clause': 'to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.'}],
            'timing': {'description': 'Judge the relative entry times, not a later inside-intersection overtake.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
        'parameter_refs': []}
    template_ref = write('template.json', template)
    needs = [{'name': term, 'unit': 'structured',
              'description': 'Retained raw source observation for ' + term}
             for term in TERMS]
    judgment = {'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE,
        'status': 'draft',
        'observable_requirements': {
            'observables': [{'name': 'drv.arrival_order', 'unit': 'structured',
                             'description': 'Original body-front entry instants and source frames'}],
            'context_inputs': [],
            'sweep_dimensions': [{'name': 'drv.arrival_order', 'unit': 'structured',
                                  'description': 'Observed relative entry order across fixed physical setups'}],
            'landmarks': [], 'recording_needs': needs,
            'limitations': ['No legal simultaneity cutoff is supplied by this stage.',
                            'Original public-highway, official-device, turning and subsection 4 evidence require later review.']}}
    judgment_ref = write('judgment-0.json', judgment)
    params = [
        {'name': 'ego_yield_wait_s', 'kind': 'controller', 'range_or_domain': 'authored nonnegative wait duration', 'used_by_laws': []},
        {'name': 'commanded_approach_speed_mps', 'kind': 'controller', 'range_or_domain': 'physically feasible approach speeds', 'used_by_laws': []},
        {'name': 'ego_speed', 'kind': 'subject_behavior', 'range_or_domain': 'observed speed history', 'used_by_laws': [LAW]},
        {'name': 'authored_other_vehicle_present', 'kind': 'world_setup', 'range_or_domain': 'boolean', 'used_by_laws': [LAW]},
        {'name': 'authored_intersection_control', 'kind': 'world_setup', 'range_or_domain': 'authored device context', 'used_by_laws': [LAW]},
    ]
    binding = {'cell_id': 'C111294', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Frozen intersection, travel and other-vehicle cell'],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [], 'variable_parameters': params}
    binding_ref = write('bindings.json', binding)
    pair = HERE.name + '__entry_pair'
    cases = []
    for suffix, wait in (('controlled_1', 1.0), ('controlled_2', 0.0)):
        cases.append({'case_id': HERE.name + '__' + suffix,
            'target_law_id': LAW, 'target_type': 'boundary_probe',
            'rationale': 'Measure body-front entry timing under fixed other-vehicle motion and a changed ego yield wait; no legal label.',
            'variable_assignments': variables(wait),
            'unresolved_judgment_calls': [PHRASE],
            'paired_probe_id': pair,
            'deliberate_differences': ['ego_yield_wait_s'],
            'probe': {'primary_variable': 'ego_yield_wait_s',
                      'comparison_or_standard': 'paired measured entry-time contrast; legal standard unresolved',
                      'target_value_or_branch': wait},
            'recording_description': recording})
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Neutral authored intersection without a crossing other vehicle.',
                'variable_assignments': variables(0.0, False),
                'unresolved_judgment_calls': [],
                'recording_description': recording}
    cases_result = {'cell_id': 'C111294', 'actor': ACTOR, 'status': 'draft',
                    'cases': [baseline, *cases],
                    'sweep_specs': [{
                        'sweep_id': 'c111294_approximate_entry_time', 'target_law_id': LAW,
                        'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                        'status': 'incomplete',
                        'rationale': 'A fixed physical entry-time sweep needs original Native feasibility and source-reviewed judgment policy.',
                        'missing_inputs': ['Original Native physically feasible entry-time range',
                                           'Source-reviewed interpretation of approximate same time']}]}
    cases_ref = write('canonical-cases.json', cases_result)
    write('cases.json', cases_result)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'status': 'draft_source_qualified_judgment_pending',
             'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': [judgment_ref],
                        'bindings': binding_ref, 'cases': cases_ref}}
    index_ref = write('semantic-index.json', index)
    print(json.dumps({'semantic_index_sha256': index_ref['sha256'],
                      'selected_cases': 2, 'judgment_calls': 1}))


if __name__ == '__main__':
    build()
