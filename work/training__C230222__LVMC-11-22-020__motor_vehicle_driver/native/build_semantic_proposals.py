"""Bind exact-law, judgment-preserving canonical proposals for C230222."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / 'proposals'
AID = ROOT.name
LAW = 'LVMC-11-22-020'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
QUOTE = ('It is unlawful for any person to drive or operate a vehicle of any kind '
         'or character in a careless or imprudent manner on any highway in the City.')
PHRASE = 'careless or imprudent manner'
NOTE = 'Qualitative manner requires review of original driving and conditions over the episode.'


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {
        'cell_id': 'C230222', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
                           'relevance_type': 'direct', 'confidence': 'high',
                           'notes': 'Curbside motor-vehicle travel can engage this City-highway driving standard; original municipal highway status remains to be verified.'}],
        'borderline_excluded': []}
    ref_relevance = write('relevance.json', relevance)
    ref_relevance_batch = write('relevance-batch.json', relevance)
    template = {
        'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'person drives or operates a vehicle on a highway in the City', 'numeric_conditions': []},
            'obligation': {'description': 'drive without a careless or imprudent manner', 'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'manner is observed across the driving episode', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
        'parameter_refs': [
            {'name': 'control_style', 'kind': 'controller', 'range_or_domain': [0, 1]},
            {'name': 'road_and_pedestrian', 'kind': 'world_setup',
             'range_or_domain': 'Native driving lane beside a sidewalk pedestrian; jurisdiction requires original review'}]}
    ref_template = write('template.json', template)
    judgment = {
        'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE, 'status': 'draft',
        'observable_requirements': {
            'observables': [
                {'name': 'kin.speed', 'unit': 'structured', 'description': 'Original Native vehicle speed series'},
                {'name': 'kin.yaw_rate', 'unit': 'structured', 'description': 'Original Native yaw series'},
                {'name': 'rel.surface_gap', 'unit': 'structured', 'description': 'Original actor-body clearance series'}],
            'context_inputs': [],
            'sweep_dimensions': [{'name': 'control_style', 'unit': 'profile_index',
                                  'description': 'Authored curbside controller profile index, held separate from realized yaw and gap'}],
            'landmarks': [],
            'recording_needs': [
                {'name': 'kin.speed', 'unit': 'structured', 'description': 'Source-joined speed over the episode'},
                {'name': 'kin.yaw_rate', 'unit': 'structured', 'description': 'Source-joined steering response over the episode'},
                {'name': 'rel.surface_gap', 'unit': 'structured', 'description': 'Source-joined participant clearance over the episode'}],
            'limitations': ['No numeric legal threshold or legal verdict follows from control requests or synthetic fixtures.',
                            'Municipal highway status and original pixels require independent review.']}}
    ref_judgment = write('judgment-manner.json', judgment)
    bindings = {
        'cell_id': 'C230222', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Authored curbside route with adjacent sidewalk walker; Native road identity and City highway status require original review'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [],
        'variable_parameters': [
            {'name': 'control_style', 'kind': 'controller', 'range_or_domain': [0, 1], 'used_by_laws': [LAW]},
            {'name': 'road_and_pedestrian', 'kind': 'world_setup',
             'range_or_domain': 'source-observed driving lane with adjacent sidewalk walker', 'used_by_laws': [LAW]}]}
    ref_bindings = write('bindings.json', bindings)
    cases = json.loads((PROPOSALS / 'cases.json').read_text())
    cases['cases'] = [case for case in cases['cases'] if case.get('target_type') != 'baseline']
    sweep = {
        'sweep_id': 'C230222-curbside-manner', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
        'rationale': 'Qualitative manner calls for source-bound physical coverage across controller requests, with legal judgment left open.',
        'status': 'complete', 'mode': 'one_dimensional', 'landmarks': [],
        'recording_description': cases['cases'][0]['recording_description'],
        'axes': [{'variable': 'control_style', 'observable': 'control_style',
                  'unit': 'profile_index', 'min': 0, 'max': 1, 'spacing': 1,
                  'range_rationale': 'The two authored controller profiles are indexed zero and one; these numbers are engineering selectors, not legal bounds.',
                  'spacing_rationale': 'Both available profiles are selected once.',
                  'feasibility_evidence': 'The source-hashed probe_a and probe_b Native constructions contain both complete 600-frame controller schedules.',
                  'measurement': {'method': 'Read the selected config profile and join its original Native motion, body and frame streams',
                                  'time_window': 'all 600 Native frames', 'statistic': 'first'}}]}
    sweep['spec_version'] = hashlib.sha256(json.dumps(sweep, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    sweep['planned_case_count'] = 2
    sweep['selection_order'] = [AID + '__probe_a', AID + '__probe_b']
    cases['sweep_specs'] = [sweep]
    for rank, case in enumerate(cases['cases']):
        case['target_type'] = 'judgment_sweep'
        case['paired_probe_id'] = sweep['sweep_id']
        case['deliberate_differences'] = ['control_style']
        case['variable_assignments']['control_style']['value'] = rank
        case['probe'] = {
            'primary_variable': 'control_style',
            'comparison_or_standard': 'Compare observed manner cues without deciding the qualitative standard',
            'target_value_or_branch': case['variable_assignments']['control_style']['value']}
        case['rationale'] = 'Source-bound curbside manner probe; actual motion, municipal highway scope and carelessness remain open.'
        case['unresolved_judgment_calls'] = [PHRASE]
        case['sweep_id'] = sweep['sweep_id']
        case['sweep_spec_version'] = sweep['spec_version']
        case['sweep_point'] = {'control_style': rank}
        case['selection_rank'] = rank
        case['judgment_refs'] = sweep['judgment_refs']
        case['sweep_measurements'] = [{'variable': 'control_style', 'observable': 'control_style',
                                       'unit': 'profile_index', 'measurement': sweep['axes'][0]['measurement']}]
    baseline = json.loads(json.dumps(cases['cases'][0]))
    baseline['case_id'] = AID + '__baseline'
    baseline['target_type'] = 'baseline'
    baseline['rationale'] = 'Shared authored curbside scene and recording contract for diagnostic comparison only.'
    baseline.pop('paired_probe_id', None)
    baseline.pop('deliberate_differences', None)
    baseline.pop('probe', None)
    for key in ('sweep_id', 'sweep_spec_version', 'sweep_point', 'selection_rank',
                'judgment_refs', 'sweep_measurements'):
        baseline.pop(key, None)
    cases['cases'].insert(0, baseline)
    cases['sweeps_expanded'] = True
    ref_cases = write('cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'status': 'draft',
             'stages': {'relevance_batch': ref_relevance_batch, 'relevance': ref_relevance,
                        'template': ref_template, 'judgment_observables': [ref_judgment],
                        'bindings': ref_bindings, 'cases': ref_cases}}
    write('semantic-index.json', index)


if __name__ == '__main__':
    main()
