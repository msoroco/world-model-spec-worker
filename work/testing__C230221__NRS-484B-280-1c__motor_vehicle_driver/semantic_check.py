"""Validate canonical semantic stage drafts with the pinned CPU contracts."""
import json
from pathlib import Path

from batch_pipeline import stages

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PROPOSALS=ROOT/'proposals'


def read(name):return json.loads((PROPOSALS/name).read_text())


def main():
    assignment=json.loads((ROOT/'assignment.json').read_text())
    request={'cell':assignment['cell'],'actor':assignment['actor']}
    common={'request':request,'law_records':{assignment['law_id']:assignment['law']},
            'dependencies':[]}
    for stage in ('relevance_batch','relevance'):
        stages.validate(stage,read(stage+'.json'),common);print(stage,'pass')
    rules=json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
    template=read('template.json')
    stages.validate('template',template,{'request':{'law_id':assignment['law_id'],
        'actor':assignment['actor']},'law_record':assignment['law'],
        'canonical_parameter_rules':rules,'dependencies':[]})
    print('template pass')
    judgment=read('judgment-1.json')
    stages.validate('judgment_observables',judgment,
       {'request':{'template_id':template['template_id'],'phrase':judgment['phrase'],
                   'note':judgment['note']},'dependencies':[]})
    print('judgment_observables pass')
    binding=read('bindings.json')
    stages.validate('bindings',binding,
      {'request':dict(request,template_ids=[template['template_id']]),
       'canonical_parameter_rules':rules,'dependencies':[template]})
    print('bindings pass')
    template['structure']['judgment_calls_needed'][0]['observable_requirements']=judgment['observable_requirements']
    stages.validate('cases',read('cases.json'),
      {'request':request,'dependencies':[binding],'templates':[template],
       'canonical_parameter_rules':rules,'judgment_completion_policy':{}})
    print('cases pass')


if __name__=='__main__':main()
