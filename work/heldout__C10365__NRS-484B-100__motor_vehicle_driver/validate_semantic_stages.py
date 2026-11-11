"""Validate all six canonical C10365 proposal stages."""

import json
from pathlib import Path

from batch_pipeline import stages


ROOT = Path(__file__).resolve().parent
assignment = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
load = lambda name: json.loads((ROOT / 'proposals' / (name + '.json')).read_text())
law, cell, actor = assignment['law'], assignment['cell'], assignment['actor']
request = {'cell': cell, 'actor': actor}
common = {'request': request, 'law_records': {law['id']: law}, 'dependencies': []}
rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
for name in ('relevance_batch', 'relevance'):
    stages.validate(name, load(name), common)
template = load('template')
stages.validate('template', template, {'request': {'law_id': law['id'], 'actor': actor},
    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
judgment = load('judgment_1')
expected = template['structure']['judgment_calls_needed'][0]
stages.validate('judgment_observables', judgment,
    {'request': {'template_id': template['template_id'],
                 'phrase': expected['phrase'], 'note': expected['note']},
     'dependencies': []})
expected['observable_requirements'] = judgment['observable_requirements']
binding = load('bindings')
stages.validate('bindings', binding,
    {'request': dict(request, template_ids=[template['template_id']]),
     'canonical_parameter_rules': rules, 'dependencies': [template]})
cases = load('cases')
stages.validate('cases', cases,
    {'request': request, 'dependencies': [binding], 'templates': [template],
     'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
selected = [row for row in cases['cases'] if row['target_type'] != 'baseline']
if len(selected) != 4:
    raise ValueError('Four exact officer indication and response cases required')
print('Four exact officer cases validate across six canonical stages')
