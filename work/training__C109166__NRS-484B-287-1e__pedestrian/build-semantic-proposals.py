"""Draft canonical stages from exact frozen law; preserve unresolved judgments."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
LAW = 'NRS-484B-287-1e'
TEMPLATE = LAW + '@pedestrian'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'proposals' / (name + '.json')
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}


def main():
    assignment = json.loads((ROOT / 'inputs' / BASE / 'assignment.json').read_text())
    quote = assignment['law']['text']
    desc = json.loads((HERE / 'config.json').read_text())['recording_description']
    phrases = [
        ('authorized to cross diagonally',
         'Original survey must establish diagonal authorization for this exact movement.',
         ['dev.regulatory_sign', 'dev.governs'], True),
        ('official traffic-control devices pertaining to such crossing movements',
         'An authored head ID and Native state are insufficient without original pixel and governance review.',
         ['dev.pedestrian_signal', 'dev.governs'], True),
        ('cross only in accordance',
         'Original complete body path and reviewed first-entry pixels remain separate from legal judgment.',
         ['kin.position', 'rel.occupies'], True),
        ('Except as provided in NRS 484B.290 [LVMC-11-30-140-B]',
         'The cross-referenced person-specific exception has no supplied original applicability evidence.',
         ['ru.pedestrian'], False)]
    refs = []
    for index, (phrase, note, names, authority) in enumerate(phrases):
        needs = [{'name': name,
                  'unit': next(channel['unit'] for channel in desc['channels'] if channel['name'] == name),
                  'description': 'Retain original source observations for independent statutory review.'}
                 for name in names]
        contexts = ([{'name': 'diagonal_authority_source', 'unit': 'source',
                      'description': 'Retain source-hashed original authority survey and review status.'}]
                    if authority else [])
        requirements = {'observables': needs, 'context_inputs': contexts,
                        'sweep_dimensions': [], 'landmarks': [],
                        'recording_needs': needs,
                        'limitations': [note, 'Synthetic diagnostic sources cannot settle original legal applicability.']}
        refs.append(write(f'judgment_observables_{index}', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': requirements}))
    relevance = {'cell_id': 'C109166', 'actor': 'pedestrian', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': ['pedestrian'],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Original diagonal authority, pixels and exception require review.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance', relevance)
    batch_ref = write('relevance_batch', relevance)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'pedestrian',
                'status': 'draft', 'quote': quote,
                'structure': {'activation': {
                    'description': 'A pedestrian is authorized by an official device to cross diagonally.',
                    'source_clause': 'When authorized to cross diagonally'},
                    'obligation': {
                    'description': 'Measure the complete crossing against the pertaining official device.',
                    'source_clause': 'cross only in accordance with the official traffic-control devices'},
                    'exceptions': [{'source_clause': 'Except as provided in NRS 484B.290 [LVMC-11-30-140-B]',
                                    'description': 'Person-specific cross-referenced exception requires source review.'}],
                    'timing': {'description': 'Join actual first road entry to original device display and path.',
                               'source_clause': 'When authorized to cross diagonally'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _, _ in phrases]},
                'parameter_refs': []}
    template_ref = write('template', template)
    binding = {'cell_id': 'C109166', 'actor': 'pedestrian', 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'requested_first_entry_instruction',
                                        'kind': 'world_setup',
                                        'range_or_domain': 'diagonal_walk or diagonal_dont_walk request',
                                        'used_by_laws': [LAW]}]}
    binding_ref = write('bindings', binding)
    cases = json.loads((HERE / 'proposals/cases.json').read_text())
    for case in cases['cases']:
        assignments = case['variable_assignments']
        assignments.pop('diagonal_authorization', None)
        case['unresolved_judgment_calls'] = [phrase for phrase, _, _, _ in phrases]
        case['recording_description'] = desc
        if case['target_type'] != 'baseline':
            case['paired_probe_id'] = 'c109166-first-entry-instruction-pair'
            case['deliberate_differences'] = ['requested_first_entry_instruction']
            case['probe'] = {
                'primary_variable': 'requested_first_entry_instruction',
                'comparison_or_standard': 'original first-entry instruction under exact clause',
                'target_value_or_branch': assignments['requested_first_entry_instruction']['value']}
    cases['sweeps_expanded'] = True
    cases['sweep_specs'] = [{'sweep_id': 'c109166-original-diagonal-authority-review',
                            'target_law_id': LAW, 'status': 'incomplete',
                            'judgment_refs': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _, _ in phrases],
                            'rationale': 'Two first-entry instruction probes are prepared; original authority and exception review remain open.',
                            'missing_inputs': ['Independently reviewed official diagonal device survey',
                                               'Original Native displayed glyph and body/boundary review',
                                               'NRS 484B.290 person-specific applicability source']}]
    cases_ref = write('cases', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': BASE,
             'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': refs,
                        'bindings': binding_ref, 'cases': cases_ref}}
    path = HERE / 'proposals/semantic-index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'semantic_index_sha256': sha(path), 'judgments': len(refs)}))


if __name__ == '__main__':
    main()
