"""Build source-bound canonical proposals for the parked-headlamp comparison."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
AID = ROOT.name
OUT = ROOT / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + path.name, 'sha256': sha(path)}


def main():
    source = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    manifest = json.loads((ROOT / 'selected-draft-execution-manifest.json').read_text())
    law, cell, actor = source['law_id'], source['cell_id'], source['actor']
    quote = source['law']['text']
    template_id = law + '@' + actor
    relevance = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law, 'quote': quote, 'applies_to': [actor],
                                    'relevance_type': 'specific_match', 'confidence': 'high',
                                    'notes': 'Original parking activity and beam pixels still require review.'}],
                 'borderline_excluded': []}
    template = {'template_id': template_id, 'law_id': law, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'Headlamps are lighted on a vehicle actually parked.',
                                   'source_clause': 'Any lighted headlamps upon a parked vehicle'},
                    'obligation': {'type': 'must',
                                   'description': 'Lighted headlamps on the parked vehicle shall be depressed or dimmed.',
                                   'source_clause': 'shall be depressed or dimmed',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Review every frame in the parked and lighted interval.'},
                    'judgment_calls_needed': [
                        {'phrase': 'parked vehicle', 'note': 'A zero-speed request alone does not prove parking rather than temporary loading.'},
                        {'phrase': 'depressed or dimmed', 'note': 'A low-beam control request alone does not prove the original beam aim or intensity.'}]},
                'parameter_refs': [
                    {'name': 'parked_headlamp_beam', 'kind': 'controller',
                     'range_or_domain': 'authored low_beam or high_beam control request'},
                    {'name': 'observed_beam_aim', 'kind': 'subject_behavior',
                     'range_or_domain': 'original source-reviewed beam elevation in degrees; unknown before capture'},
                    {'name': 'observed_beam_intensity', 'kind': 'subject_behavior',
                     'range_or_domain': 'original source-reviewed relative intensity; unknown before capture'}]}
    judgments = []
    for index, (phrase, note, observations) in enumerate((
            ('parked vehicle', 'A zero-speed request alone does not prove parking rather than temporary loading.',
             [('drv.standing_or_parked', 'state', 'Original activity review and body pose'),
              ('kin.velocity', 'm/s', 'Original velocity throughout the interval'),
              ('rel.occupies', 'state', 'Original footprint and curb lane')]),
            ('depressed or dimmed', 'A low-beam control request alone does not prove the original beam aim or intensity.',
             [('sig.headlamp', 'state', 'Original lamp readback and source-reviewed beam aim and intensity pixels')]))):
        items = [{'name': name, 'unit': unit, 'description': description}
                 for name, unit, description in observations]
        proposal = {'template_id': template_id, 'phrase': phrase, 'note': note,
                    'status': 'draft', 'observable_requirements': {
                        'observables': items, 'context_inputs': [], 'sweep_dimensions': [],
                        'landmarks': [], 'recording_needs': items,
                        'limitations': ['Original Native and pixel review remain required; no legal verdict is assigned.']}}
        judgments.append(write('judgment-' + str(index + 1), proposal))
    bindings = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                'established_contexts': [{'name': 'sloped_curb_parked_vehicle',
                                          'source': 'frozen catalog cell and exact law text'}],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [
                    {'name': 'parked_headlamp_beam', 'kind': 'controller',
                     'range_or_domain': 'low_beam or high_beam requested', 'used_by_laws': [law]},
                    {'name': 'observed_beam_aim', 'kind': 'subject_behavior',
                     'range_or_domain': 'original source-reviewed beam elevation', 'used_by_laws': [law]},
                    {'name': 'observed_beam_intensity', 'kind': 'subject_behavior',
                     'range_or_domain': 'original source-reviewed beam intensity', 'used_by_laws': [law]}]}
    old_cases = [c for c in json.loads((OUT / 'cases.json').read_text())['cases']
                 if c['target_type'] != 'baseline']
    constructions = {e['case_id']: json.loads((ROOT / e['construction']).read_text())
                     for e in manifest['cases']}
    for case in old_cases:
        case['recording_description'] = constructions[case['case_id']]['recording_description']
        case['probe'] = {'primary_variable': 'parked_headlamp_beam',
                         'comparison_or_standard': 'original beam aim and intensity contrast; legal judgment unresolved',
                         'target_value_or_branch': case['variable_assignments']['parked_headlamp_beam']['value']}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Shared stationary sloped-curb context; no original Native observation is claimed.',
                'variable_assignments': {
                    'parked_headlamp_beam': {'kind': 'controller', 'value': 'low_beam'},
                    'observed_beam_aim': {'kind': 'subject_behavior', 'value': None},
                    'observed_beam_intensity': {'kind': 'subject_behavior', 'value': None}},
                'unresolved_judgment_calls': [],
                'recording_description': old_cases[0]['recording_description']}
    sweep = {'sweep_id': 'parked-lamp-judgment-coverage', 'target_law_id': law,
             'status': 'incomplete',
             'judgment_refs': template['structure']['judgment_calls_needed'],
             'rationale': 'Original parked activity, beam aim and beam intensity require physical source review; no legal cutoff is supplied.',
             'missing_inputs': ['A source-backed physical range and feasible controllable beam setpoints for systematic judgment coverage; existing low/high comparison is retained.']}
    cases = {'cell_id': cell, 'actor': actor, 'status': 'draft', 'sweep_specs': [sweep],
             'cases': [baseline, *old_cases], 'sweeps_expanded': True}
    stages = {'relevance_batch': write('relevance_batch', relevance),
              'relevance': write('relevance', relevance),
              'template': write('template', template),
              'judgment_observables': judgments,
              'bindings': write('bindings', bindings),
              'cases': write('cases', cases)}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
             'stages': stages, 'status': 'draft', 'original_native_observed': False}
    write('semantic-index', index)
    print(json.dumps({'semantic_index_sha256': sha(OUT / 'semantic-index.json'),
                      'selected_cases': len(old_cases)}))


if __name__ == '__main__':
    main()
