"""Validate the authored source-law stages available before case manifest binding."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


def main():
    assignment = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
    proposals = FOLDER / 'proposals'
    request = {'cell': assignment['cell'], 'actor': assignment['actor']}
    common = {'request': request, 'law_records': {assignment['law_id']: assignment['law']},
              'dependencies': []}
    for name in ('relevance_batch', 'relevance'):
        stages.validate(name, json.loads((proposals / (name + '.json')).read_text()), common)
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    template = json.loads((proposals / 'template.json').read_text())
    stages.validate('template', template, {'request': {'law_id': assignment['law_id'],
                    'actor': assignment['actor']}, 'law_record': assignment['law'],
                    'canonical_parameter_rules': rules, 'dependencies': []})
    for index, judgment in enumerate(template['structure']['judgment_calls_needed'], 1):
        result = json.loads((proposals / f'judgment_observables_{index}.json').read_text())
        stages.validate('judgment_observables', result, {'request': {
            'template_id': template['template_id'], 'phrase': judgment['phrase'],
            'note': judgment['note']}, 'dependencies': []})
    binding = json.loads((proposals / 'bindings.json').read_text())
    stages.validate('bindings', binding, {'request': dict(request,
                    template_ids=[template['template_id']]), 'canonical_parameter_rules': rules,
                    'dependencies': [template]})
    print('semantic relevance, template, four judgment observables, and bindings pass current stage validators')


if __name__ == '__main__':
    main()
