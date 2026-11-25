"""Validate all C126120 canonical draft stages against the pinned CPU runtime."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
if not OUTPUT or not Path(OUTPUT).resolve().is_relative_to(REPO / '.runtime-work'):
    raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


def read(path):
    return json.loads(Path(path).read_text())


def main():
    assignment = read(REPO / 'inputs' / ROOT.name / 'assignment.json')
    refs = read(ROOT / 'proposals/semantic-index.json')['stages']
    def stage(name):
        reference = refs[name]
        path = ROOT / reference['path']
        import hashlib
        if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('Stale semantic stage source: ' + name)
        return read(path)
    request = {'cell': assignment['cell'], 'actor': assignment['actor']}
    common = {'request': request, 'law_records': {assignment['law_id']: assignment['law']},
              'dependencies': []}
    for name in ('relevance_batch', 'relevance'):
        stages.validate(name, stage(name), common)
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    template = stage('template')
    stages.validate('template', template, {'request': {'law_id': assignment['law_id'],
        'actor': assignment['actor']}, 'law_record': assignment['law'],
        'canonical_parameter_rules': rules, 'dependencies': []})
    binding = stage('bindings')
    stages.validate('bindings', binding, {'request': dict(request,
        template_ids=[template['template_id']]), 'canonical_parameter_rules': rules,
        'dependencies': [template]})
    cases = stage('cases')
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
        'templates': [template], 'canonical_parameter_rules': rules,
        'judgment_completion_policy': {}})
    print(json.dumps({'assignment_id': ROOT.name, 'canonical_stages_valid': True,
                      'cases': len(cases['cases']), 'selected_cases': len(cases['cases']) - 1,
                      'native_or_legal_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
