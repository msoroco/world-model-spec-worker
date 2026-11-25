"""Author the exact C188132 law-to-case semantic proposal chain."""
from __future__ import annotations

import json
from pathlib import Path
from overpass_source import CASES, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW = 'LVMC-11-30-060-B'
TEMPLATE = LAW + '@pedestrian'
LAW_TEXT = ('Any pedestrian crossing a roadway at a point where a pedestrian tunnel or overhead pedestrian crossing has been provided '
            'shall yield the right-of-way to all vehicles upon the roadway. The foregoing rules in this Section shall have '
            'no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing '
            'at certain designated places.')
JUDGMENTS = [
    ('overhead pedestrian crossing has been provided',
     'Source review and original pixels must establish provided overhead structure and access.',
     'provided_overhead_crossing', 'structured'),
    ('yield the right-of-way to all vehicles upon the roadway',
     'Retain original pedestrian crossing timing and every Native roadway vehicle; legal yielding remains unresolved.',
     'crossing_order', 'structured'),
    ('pedestrians are prohibited from crossing at certain designated places',
     'The Section 11.30.070 designation requires independently sourced municipal review.',
     'designated_place_prohibition', 'boolean'),
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    proposal = ROOT / 'proposals'
    input_path = REPO / 'inputs' / ASSIGNMENT / 'assignment.json'
    source = {'path': 'inputs/' + ASSIGNMENT + '/assignment.json', 'sha256': sha(input_path)}
    relevance = {'cell_id': 'C188132', 'actor': 'pedestrian', 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': LAW_TEXT,
                           'applies_to': ['pedestrian'],
                           'relevance_type': 'roadway crossing at a provided overhead crossing',
                           'confidence': 'low',
                           'notes': 'Authored deck is a candidate; original provision/access and designation need separate review.'}],
        'borderline_excluded': []}
    write(proposal / 'relevance_batch.json', relevance)
    write(proposal / 'relevance.json', relevance)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'pedestrian',
        'quote': LAW_TEXT, 'status': 'draft',
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'A pedestrian crosses the roadway at a point with a provided tunnel or overhead crossing.',
                           'numeric_conditions': []},
            'obligation': {'description': 'The pedestrian yields the right-of-way to all vehicles upon the roadway.',
                           'type': 'pedestrian_crossing_yield', 'numeric_conditions': []},
            'exceptions': [{'source_clause': 'The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.',
                            'description': 'Designated prohibited crossing place under Section 11.30.070.'}],
            'timing': {'description': 'Observe original 20 Hz pedestrian crossing and every roadway vehicle for the complete attempt.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in JUDGMENTS]},
        'parameter_refs': [{'name': 'entry_control_policy', 'kind': 'controller'},
                           {'name': 'designated_prohibition_context', 'kind': 'world_setup'}]}
    write(proposal / 'template.json', template)
    judgment_paths = []
    for index, (phrase, note, key, unit) in enumerate(JUDGMENTS, 1):
        observable = {'name': key, 'unit': unit, 'description': note}
        result = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
                  'observable_requirements': {'observables': [observable],
                      'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                      'recording_needs': [observable],
                      'limitations': ['Engineering observations do not settle legal yielding or site designation.']}}
        path = proposal / ('judgment-' + str(index) + '.json')
        write(path, result)
        judgment_paths.append(path)
    binding = {'cell_id': 'C188132', 'actor': 'pedestrian', 'status': 'draft',
        'established_contexts': ['Source-hashed overpass candidate above surface roadway; original provision remains review-gated.'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [{'name': 'crossing_map', 'kind': 'world_setup',
                              'range_or_domain': 'same source-hashed OpenDRIVE surface and deck'},
                             {'name': 'participant_routes', 'kind': 'world_setup',
                              'range_or_domain': 'same pedestrian and roadway vehicle route geometry'}],
        'variable_parameters': [
            {'name': 'entry_control_policy', 'kind': 'controller',
             'range_or_domain': 'hold until vehicle passes; enter without hold',
             'used_by_laws': [LAW]},
            {'name': 'designated_prohibition_context', 'kind': 'world_setup',
             'range_or_domain': 'absent; source-backed designated prohibition',
             'used_by_laws': [LAW]}]}
    write(proposal / 'bindings.json', binding)
    cases = json.loads((proposal / 'cases.json').read_text())
    cases['status'] = 'draft'
    cases['sweep_specs'] = [
        {'sweep_id': 'c188132-judgment-' + str(index), 'target_law_id': LAW,
         'status': 'incomplete', 'judgment_refs': [{'phrase': phrase, 'note': note}],
         'rationale': 'No numerical legal boundary follows from candidate geometry or controller requests.',
         'missing_inputs': ['independently reviewed original Native source and legal site context']}
        for index, (phrase, note, _, _) in enumerate(JUDGMENTS, 1)]
    for case in cases['cases']:
        variant = case['case_id'].split('__')[-1]
        hold = variant in ('semantic_baseline', 'yield_before_vehicle')
        prohibited = variant == 'designated_prohibition'
        case['variable_assignments'] = {
            'entry_control_policy': {'kind': 'controller',
                                     'value': 'hold_until_vehicle_passes' if hold else 'enter_without_hold'},
            'designated_prohibition_context': {'kind': 'world_setup',
                                               'value': 'designated_prohibition' if prohibited else 'absent'}}
        case['unresolved_judgment_calls'] = [phrase for phrase, _, _, _ in JUDGMENTS]
        if variant == 'semantic_baseline':
            continue
        case['target_type'] = 'boundary_probe'
        variable = 'designated_prohibition_context' if prohibited else 'entry_control_policy'
        case['paired_probe_id'] = 'designated_exception' if prohibited else 'entry_timing'
        case['deliberate_differences'] = [variable]
        case['probe'] = {'primary_variable': variable,
                         'comparison_or_standard': 'controlled source context contrast' if prohibited else 'controlled pedestrian entry timing',
                         'target_value_or_branch': variant}
    write(proposal / 'cases.json', cases)
    refs = {'relevance_batch': proposal/'relevance_batch.json',
            'relevance': proposal/'relevance.json', 'template': proposal/'template.json',
            'judgment_observables': judgment_paths,
            'bindings': proposal/'bindings.json', 'cases': proposal/'cases.json'}
    def ref(path):
        return {'path': 'proposals/' + path.name, 'sha256': sha(path)}
    write(proposal/'semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ASSIGNMENT, 'source': source,
        'stages': {key: [ref(path) for path in value] if isinstance(value, list) else ref(value)
                   for key, value in refs.items()},
        'status': 'draft_original_site_and_Native_review_pending'})


if __name__ == '__main__':
    main()
