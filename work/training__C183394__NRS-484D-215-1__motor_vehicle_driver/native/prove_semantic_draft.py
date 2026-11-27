"""Validate the source-grounded canonical stages completed so far."""
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
REPO = next(parent for parent in PACKAGE.parents if (parent / 'batch.json').is_file())
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


def read(path):
    return json.loads(path.read_text())


proposal = PACKAGE / 'proposals'
assignment = read(REPO / 'inputs' / PACKAGE.name / 'assignment.json')
law = assignment['law']
request = {'cell': assignment['cell'], 'actor': assignment['actor']}
common = {'request': request, 'law_records': {law['id']: law}, 'dependencies': []}
for stage in ('relevance_batch', 'relevance'):
    stages.validate(stage, read(proposal / (stage + '.json')), common)
rules = read(REPO / 'runtime/scenario_pipeline/data/canonical_parameter_aliases.json')
template = read(proposal / 'template.json')
stages.validate('template', template, {'request': {'law_id': law['id'],
                 'actor': assignment['actor']}, 'law_record': law,
                 'canonical_parameter_rules': rules, 'dependencies': []})
for index, judgment in enumerate(template['structure']['judgment_calls_needed']):
    result = read(proposal / ('judgment_observables_' + str(index) + '.json'))
    stages.validate('judgment_observables', result,
                    {'request': {'template_id': template['template_id'],
                                 'phrase': judgment['phrase'], 'note': judgment['note']},
                     'dependencies': []})
binding = read(proposal / 'bindings.json')
stages.validate('bindings', binding,
                {'request': dict(request, template_ids=[template['template_id']]),
                 'canonical_parameter_rules': rules, 'dependencies': [template]})
print('PASS: canonical relevance, template, three judgments, and bindings')
