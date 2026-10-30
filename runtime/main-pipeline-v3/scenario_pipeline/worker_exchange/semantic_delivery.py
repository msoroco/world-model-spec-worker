"""CPU-only validation of worker-authored canonical stage proposals.

The worker sees law/cell inputs and pure stage contracts, never local SQLite.
The local adopter binds these same source-hashed proposals to actual jobs.
"""
from copy import deepcopy
import json
from pathlib import Path

from .common import read, sha, within

STAGES = ('relevance_batch', 'relevance', 'template',
          'judgment_observables', 'bindings', 'cases')


def validate(folder, assignment, manifest):
    from batch_pipeline import stages

    folder = Path(folder)
    index = read(folder / 'proposals/semantic-index.json')
    if index.get('format') != 'worker-semantic-delivery-v1' or index.get('assignment_id') != assignment['assignment_id']:
        raise ValueError('Wrong semantic delivery identity')
    references = index.get('stages')
    if not isinstance(references, dict) or set(references) != set(STAGES):
        raise ValueError('Incomplete semantic delivery stage chain')

    def load(reference):
        if not isinstance(reference, dict) or not reference.get('path') or not reference.get('sha256'):
            raise ValueError('Stage proposal needs a path and SHA-256')
        path = within(folder, reference['path'])
        if not path.is_file() or sha(path) != reference['sha256']:
            raise ValueError('Stage proposal source hash changed')
        return deepcopy(read(path))

    law_id, cell_id, actor = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
    law = assignment.get('law')
    if not isinstance(law, dict) or law.get('id') != law_id or not law.get('text'):
        raise ValueError('Assignment lacks exact law text')
    cell = assignment.get('cell')
    if not isinstance(cell, dict) or cell.get('cell_id') != cell_id:
        raise ValueError('Assignment lacks exact catalog cell')
    request = {'cell': cell, 'actor': actor}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    relevance = []
    for stage in ('relevance_batch', 'relevance'):
        result = load(references[stage])
        stages.validate(stage, result, deepcopy(common))
        if [item['law_id'] for item in result['relevant_laws']] != [law_id]:
            raise ValueError('Semantic relevance must select the assigned law exactly')
        relevance.append(result)
    if relevance[0] != relevance[1]:
        raise ValueError('Batch and cell relevance results disagree')

    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    template = load(references['template'])
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    judgments = template['structure']['judgment_calls_needed']
    refs = references['judgment_observables']
    if not isinstance(refs, list) or len(refs) != len(judgments):
        raise ValueError('Every judgment phrase needs one observable proposal')
    observed = []
    for expected, reference in zip(judgments, refs):
        result = load(reference)
        stages.validate('judgment_observables', result,
                        {'request': {'template_id': template['template_id'],
                                     'phrase': expected['phrase'], 'note': expected.get('note', '')},
                         'dependencies': []})
        if (result['phrase'], result.get('note', '')) != (expected['phrase'], expected.get('note', '')):
            raise ValueError('Judgment observables changed the phrase order')
        expected['observable_requirements'] = result['observable_requirements']
        observed.append(result)

    binding = load(references['bindings'])
    stages.validate('bindings', binding, {'request': dict(request, template_ids=[template['template_id']]),
                    'canonical_parameter_rules': rules, 'dependencies': [template]})
    if [item['template_id'] for item in binding['law_refs']] != [template['template_id']]:
        raise ValueError('Assigned law must be an active binding')
    cases = load(references['cases'])
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
                    'templates': [template], 'canonical_parameter_rules': rules,
                    'judgment_completion_policy': {}})
    selected = {item['case_id']: item for item in cases['cases'] if item['target_type'] != 'baseline'}
    if set(selected) != {item['case_id'] for item in manifest['cases']}:
        raise ValueError('Canonical cases differ from selected delivery cases')
    for entry in manifest['cases']:
        construction = read(within(folder, entry['construction']))
        if selected[entry['case_id']]['recording_description'] != construction['recording_description']:
            raise ValueError('Canonical case changed the recording description')
    return {'stage_count': 5 + len(observed), 'selected_cases': len(selected),
            'index_sha256': sha(folder / 'proposals/semantic-index.json')}
