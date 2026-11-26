"""Author canonical source-bound proposals for six flashing-red comparisons."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
PROPOSALS = ROOT / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = SCRATCH / (path.name + '.semantic-stage')
    staged.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.replace(staged, path)


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    assignment = json.loads((REPO / 'inputs' / plan['assignment_id'] / 'assignment.json').read_text())
    quote = assignment['law']['text']
    aid, law_id, cell_id, actor = (plan[key] for key in ('assignment_id', 'law_id', 'cell_id', 'actor'))
    template_id = law_id + '@' + actor
    common = {'cell_id': cell_id, 'actor': actor, 'status': 'draft'}
    relevance = dict(common, relevant_laws=[{'law_id': law_id, 'quote': quote,
        'applies_to': [actor], 'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'Frozen flashing-red intersection cell and motor-vehicle driver scope.'}],
        borderline_excluded=[])
    put(PROPOSALS / 'relevance-batch.json', relevance)
    put(PROPOSALS / 'relevance.json', relevance)
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': quote,
        'structure': {'law_id': law_id,
            'activation': {'condition': 'Official device uses rapid intermittent red flashes governing the approaching driver.', 'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': 'Stop before the marked limit line, otherwise nearest crosswalk, otherwise the intersection; right to proceed follows required-stop rules.', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Before entering the applicable reference, then before proceeding under required-stop rules.', 'numeric_conditions': []},
            'judgment_calls_needed': []},
        'parameter_refs': []}
    put(PROPOSALS / 'template.json', template)
    variables = [
        {'name': 'stopping_reference_kind', 'kind': 'world_setup',
         'range_or_domain': 'limit_line, crosswalk, or intersection under statutory hierarchy',
         'used_by_laws': [law_id]},
        {'name': 'requested_pre_reference_halt', 'kind': 'controller',
         'range_or_domain': 'true or false request; original stop measured separately',
         'used_by_laws': [law_id]},
        {'name': 'observed_full_stop', 'kind': 'subject_behavior',
         'range_or_domain': 'original source observation or unknown',
         'used_by_laws': [law_id]}]
    binding = dict(common, established_contexts=[{'name': 'flashing_red_intersection',
        'source': 'Frozen C111271 catalog cell; official governance and reference require Native source review.'}],
        law_refs=[{'template_id': template_id, 'binding_kind': 'direct'}],
        context_refs=[], fixed_parameters=[], variable_parameters=variables)
    put(PROPOSALS / 'bindings.json', binding)
    recording = json.loads((ROOT / 'native/config.json').read_text())['recording_description']
    baseline = dict(common, case_id=aid + '__baseline', target_law_id=None,
        target_type='baseline', rationale='Unselected neutral definition with no original capture.',
        variable_assignments={'stopping_reference_kind': {'kind': 'world_setup', 'value': 'neutral', 'unit': 'categorical'},
            'requested_pre_reference_halt': {'kind': 'controller', 'value': False, 'unit': 'boolean'},
            'observed_full_stop': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}},
        unresolved_judgment_calls=[], recording_description=recording)
    cases = [baseline]
    for source in plan['cases']:
        case_id = source['case_id']
        cases.append(dict(common, case_id=case_id, target_law_id=law_id,
            target_type=source['target_type'], rationale=source['physical_target'] + '; original outcome remains unverified.',
            paired_probe_id=source['reference_kind'] + '_stop_pair',
            deliberate_differences=['requested_pre_reference_halt'],
            probe={'primary_variable': 'requested_pre_reference_halt',
                   'comparison_or_standard': 'same-reference requested-control pair; no legal cutoff',
                   'target_value_or_branch': str(source['halt_requested']).lower()},
            variable_assignments={'stopping_reference_kind': {'kind': 'world_setup',
                'value': source['reference_kind'], 'unit': 'categorical'},
                'requested_pre_reference_halt': {'kind': 'controller',
                'value': source['halt_requested'], 'unit': 'boolean'},
                'observed_full_stop': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}},
            unresolved_judgment_calls=[], recording_description=recording))
    put(PROPOSALS / 'cases.json', dict(common, sweeps_expanded=True, sweep_specs=[], cases=cases))
    paths = {stage: PROPOSALS / name for stage, name in (
        ('relevance_batch', 'relevance-batch.json'), ('relevance', 'relevance.json'),
        ('template', 'template.json'), ('bindings', 'bindings.json'),
        ('cases', 'cases.json'))}
    refs = {stage: {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
            for stage, path in paths.items()}
    refs['judgment_observables'] = []
    put(PROPOSALS / 'semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': aid, 'stages': refs})
    print(json.dumps({'selected_cases': len(plan['cases']),
                      'semantic_index_sha256': sha(PROPOSALS / 'semantic-index.json')}))


if __name__ == '__main__':
    main()
