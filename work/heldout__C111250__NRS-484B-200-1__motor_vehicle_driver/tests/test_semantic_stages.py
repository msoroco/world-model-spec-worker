from __future__ import annotations
import unittest, hashlib, json, copy, sys
from pathlib import Path

class SemanticStagesTests(unittest.TestCase):
 def test_canonical_semantic_stage_chain(self):
  folder=Path(__file__).resolve().parents[1];repo=folder.parents[1]
  sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
  from batch_pipeline import stages
  load=lambda name:json.loads((folder/'proposals'/name).read_text())
  assignment=json.loads((repo/'inputs'/folder.name/'assignment.json').read_text())
  index=load('semantic-index.json');self.assertEqual(index['assignment_id'],folder.name)
  for ref in index['stages'].values():
   for item in (ref if isinstance(ref,list) else [ref]):
    self.assertEqual(hashlib.sha256((folder/item['path']).read_bytes()).hexdigest(),item['sha256'])
  rules=json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
  request={'cell':assignment['cell'],'actor':assignment['actor']}
  common={'request':request,'law_records':{assignment['law_id']:assignment['law']},'dependencies':[]}
  for stage in ('relevance_batch','relevance'):
   stages.validate(stage,load('relevance.json'),copy.deepcopy(common))
  template=load('template.json')
  stages.validate('template',template,{'request':{'law_id':assignment['law_id'],'actor':assignment['actor']},'law_record':assignment['law'],'canonical_parameter_rules':rules,'dependencies':[]})
  judgment=load('judgment_sufficient_width.json');entry=template['structure']['judgment_calls_needed'][0]
  stages.validate('judgment_observables',judgment,{'request':{'template_id':template['template_id'],'phrase':entry['phrase'],'note':entry['note']},'dependencies':[]})
  entry['observable_requirements']=judgment['observable_requirements']
  binding=load('bindings.json')
  stages.validate('bindings',binding,{'request':dict(request,template_ids=[template['template_id']]),'canonical_parameter_rules':rules,'dependencies':[template]})
  cases=load('cases.json')
  stages.validate('cases',cases,{'request':request,'dependencies':[binding],'templates':[template],'canonical_parameter_rules':rules,'judgment_completion_policy':{}})
  self.assertEqual(sum(c['target_type']!='baseline' for c in cases['cases']),12)

if __name__ == "__main__":
 unittest.main()
