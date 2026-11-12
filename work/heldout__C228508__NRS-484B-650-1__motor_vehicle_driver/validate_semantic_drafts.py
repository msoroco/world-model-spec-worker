"""Validate authored partial semantic stages against pinned stage contracts."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    source = HERE / 'proposals'
    read = lambda name: json.loads((source / name).read_text())
    request = {'cell': assignment['cell'], 'actor': assignment['actor']}
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    for name in ('relevance_batch', 'relevance'):
        stages.validate(name, read(name + '.json'),
                        {'request': request, 'law_records': {assignment['law_id']: assignment['law']},
                         'dependencies': []})
    template = read('template.json')
    stages.validate('template', template,
                    {'request': {'law_id': assignment['law_id'], 'actor': assignment['actor']},
                     'law_record': assignment['law'],
                     'canonical_parameter_rules': rules, 'dependencies': []})
    for slug in ('too_closely', 'unsafe_lane', 'immediate_hazard'):
        proposal = read('judgment_' + slug + '.json')
        stages.validate('judgment_observables', proposal,
                        {'request': {'template_id': template['template_id'],
                                     'phrase': proposal['phrase'], 'note': proposal['note']},
                         'dependencies': []})
    stages.validate('bindings', read('bindings.json'),
                    {'request': dict(request, template_ids=[template['template_id']]),
                     'canonical_parameter_rules': rules, 'dependencies': [template]})
    print('PASS relevance_batch, relevance, template, three judgment observables, bindings')


if __name__ == '__main__':
    main()
