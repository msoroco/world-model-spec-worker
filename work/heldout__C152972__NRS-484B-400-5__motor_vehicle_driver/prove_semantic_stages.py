"""Recheck the returned semantic stages without a simulator or local database."""

import copy
import json
import sys
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline.stages import validate  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def main():
    assignment = read(ROOT / 'inputs' / FOLDER.name / 'assignment.json')
    proposals = FOLDER / 'proposals'
    request = {'cell': assignment['cell'], 'actor': assignment['actor']}
    relevance = read(proposals / 'relevance.json')
    for stage in ('relevance_batch', 'relevance'):
        validate(stage, copy.deepcopy(relevance), {'request': request,
                 'law_records': {assignment['law_id']: assignment['law']},
                 'dependencies': []})
    rules = read(ROOT / 'runtime/scenario_pipeline/data/canonical_parameter_aliases.json')
    template = read(proposals / 'template.json')
    validate('template', copy.deepcopy(template), {'request': {'law_id': assignment['law_id'],
             'actor': assignment['actor']}, 'law_record': assignment['law'],
             'canonical_parameter_rules': rules, 'dependencies': []})
    judgments = template['structure']['judgment_calls_needed']
    for number, expected in enumerate(judgments, 1):
        observation = read(proposals / f'judgment_{number}.json')
        validate('judgment_observables', copy.deepcopy(observation),
                 {'request': {'template_id': template['template_id'],
                              'phrase': expected['phrase'], 'note': expected.get('note', '')},
                  'dependencies': []})
        expected['observable_requirements'] = observation['observable_requirements']
    binding = read(proposals / 'bindings.json')
    validate('bindings', copy.deepcopy(binding),
             {'request': dict(request, template_ids=[template['template_id']]),
              'canonical_parameter_rules': rules, 'dependencies': [template]})
    cases = read(proposals / 'cases.json')
    validate('cases', copy.deepcopy(cases),
             {'request': request, 'dependencies': [binding], 'templates': [template],
              'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    print(json.dumps({'stages_validated': 7, 'cases': len(cases['cases']),
                      'sweeps': len(cases['sweep_specs']),
                      'selected_case_ids': [c['case_id'] for c in cases['cases']
                                            if c['target_type'] != 'baseline']}, indent=2))


if __name__ == '__main__':
    main()
