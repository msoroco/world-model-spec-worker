"""Author exact-law draft semantic stage chain for the selected four cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'unless directed otherwise by another device as provided in NRS 484B.283'
NOTE = 'Whether another device physically directs this crossing requires original pixel, facing, and governance review.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    folder = HERE / 'proposals'
    folder.mkdir(exist_ok=True)
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Conditional pedestrian crossing permission; original governing direction and pixels require saved review.'}],
                 'borderline_excluded': []}
    for name in ('relevance_batch', 'relevance'):
        write(folder / (name + '.json'), relevance)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': QUOTE,
                'structure': {
                    'activation': {'description': 'Pedestrian faces a circular-green-alone signal at first crosswalk entry.',
                                   'source_clause': 'When the signal is circular green alone'},
                    'obligation': {'description': 'Conditional permission to proceed across a marked or unmarked crosswalk; no violation label follows from this permission.',
                                   'source_clause': 'may proceed across the highway within any marked or unmarked crosswalk'},
                    'exceptions': [{'source_clause': PHRASE,
                                    'description': 'Another governing pedestrian device may direct otherwise under the cited NRS 484B.283 provisions.'}],
                    'timing': {'description': 'Measure displayed indication and governing direction at first crosswalk entry, then retain crossing history.',
                               'source_clause': 'may proceed across the highway'},
                    'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': []}
    write(folder / 'template.json', template)
    observed = {'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE,
                'status': 'draft',
                'observable_requirements': {
                    'observables': [{'name': 'pedestrian_entry_signal', 'unit': 'structured',
                                     'description': 'First crosswalk entry, facing circular head, pedestrian head and frame joins.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [{'name': 'pedestrian_entry_signal', 'unit': 'structured',
                                         'description': 'Original Native pose/readback and independently reviewed source pixels.'}],
                    'limitations': ['Requested state and Native actor readback cannot establish displayed pixels or whether the device governs the crossing.']}}
    write(folder / 'judgment_observables_0.json', observed)
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_pedestrian_indication', 'kind': 'world_setup',
                    'range_or_domain': 'Walk or steady Do Not Walk; construction request only',
                    'used_by_laws': [LAW]},
                   {'name': 'observed_entry_signal', 'kind': 'subject_behavior',
                    'range_or_domain': 'source-observed circular green and governing pedestrian direction at first entry',
                    'used_by_laws': [LAW]}]}
    write(folder / 'bindings.json', binding)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    construction = json.loads((HERE / 'v2-primary/witness_1/construction.json').read_text())
    recording = construction['recording_description']
    assignments = lambda state: {
        'requested_pedestrian_indication': {'kind': 'world_setup', 'value': state},
        'observed_entry_signal': {'kind': 'subject_behavior', 'value': None}}
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Shared authored geometry with no selected state.',
              'variable_assignments': assignments(None),
              'recording_description': recording,
              'unresolved_judgment_calls': [PHRASE]}]
    for item in plan['cases']:
        suffix = item['case_id'].rsplit('__', 1)[-1]
        state = 'dont_walk' if suffix.endswith('2') else 'walk'
        group = 'c111331-witness-pair' if suffix.startswith('witness') else 'c111331-deferral-pair'
        case_construction = json.loads((HERE / 'v2-primary' / suffix / 'construction.json').read_text())
        cases.append({'case_id': item['case_id'], 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'rationale': 'Compare original first-entry signal observations with the other authored conditions fixed; leave legal judgment unresolved.',
                      'paired_probe_id': group,
                      'deliberate_differences': ['requested_pedestrian_indication'],
                      'probe': {'primary_variable': 'requested_pedestrian_indication',
                                'comparison_or_standard': 'source-reviewed pedestrian direction at first crosswalk entry',
                                'target_value_or_branch': state},
                      'variable_assignments': assignments(state),
                      'recording_description': case_construction['recording_description'],
                      'unresolved_judgment_calls': [PHRASE]})
    proposal = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': cases,
                'sweep_specs': [{'sweep_id': 'c111331-original-device-governance',
                                 'target_law_id': LAW,
                                 'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                                 'rationale': 'A numeric physical sweep cannot determine whether another displayed device legally directs this crossing; independently review original pixels and facing/governance.',
                                 'status': 'incomplete',
                                 'missing_inputs': ['Original Native source pixels and independent device-governance review are not present in CPU fixtures.']}],
                'sweeps_expanded': True}
    write(folder / 'cases.json', proposal)
    stages = {}
    for name in ('relevance_batch', 'relevance', 'template', 'judgment_observables_0', 'bindings', 'cases'):
        path = folder / (name + '.json')
        ref = {'path': 'proposals/' + name + '.json', 'sha256': sha(path)}
        if name == 'judgment_observables_0':
            stages['judgment_observables'] = [ref]
        else:
            stages[name] = ref
    write(folder / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                            'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'semantic_cases': len(cases), 'judgment_status': 'unresolved'}))


if __name__ == '__main__':
    main()
