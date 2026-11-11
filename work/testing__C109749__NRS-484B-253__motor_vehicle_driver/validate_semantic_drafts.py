"""Validate authored semantic stages before the unfinished case-stage chain."""
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
sys.path.insert(0, str(repo/'runtime/scenario_pipeline'))
sys.path.insert(1, str(repo/'runtime/python'))
from batch_pipeline import stages

proposal = folder/'proposals'
assignment = json.loads((repo/'inputs'/folder.name/'assignment.json').read_text())
law = assignment['law']
request = {'cell':assignment['cell'], 'actor':assignment['actor']}


def read(name):
    return json.loads((proposal/name).read_text())


common = {'request':request, 'law_records':{assignment['law_id']:law}, 'dependencies':[]}
for name, stage in [('relevance-batch.json','relevance_batch'),('relevance.json','relevance')]:
    stages.validate(stage, read(name), common)
    print('passed',name)
rules = json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
template = read('template.json')
stages.validate('template', template, {'request':{'law_id':assignment['law_id'],
    'actor':assignment['actor']}, 'law_record':law, 'canonical_parameter_rules':rules,
    'dependencies':[]})
print('passed template.json')
for number, judgment in enumerate(template['structure']['judgment_calls_needed'],1):
    name = f'judgment-observables-{number}.json'
    stages.validate('judgment_observables',read(name),{'request':{
        'template_id':template['template_id'],'phrase':judgment['phrase'],
        'note':judgment['note']},'dependencies':[]})
    print('passed',name)
stages.validate('bindings', read('bindings.json'), {'request':dict(request,
    template_ids=[template['template_id']]), 'canonical_parameter_rules':rules,
    'dependencies':[template]})
print('passed bindings.json')
