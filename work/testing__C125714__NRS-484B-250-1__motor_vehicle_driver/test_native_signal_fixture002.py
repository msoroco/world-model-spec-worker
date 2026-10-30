import importlib.util
from pathlib import Path
import unittest
import networkx as nx
from traffic_spec_adapter.adapter import device_record
OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('signal_fixture',OWN/'native_signal_fixture002.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class SignalDiagnostic(unittest.TestCase):
 def test_raw_state_and_other_route_governance(self):
  g=nx.MultiDiGraph();report=helper.augment_graph(g,{'signal_actor_id':7,'signal_state':'Red','requested_state':'Green','affected_lanes':[[3,0,-1]],'facing_subject':False})
  n=report['added_nodes'][0];key,d=device_record(n,g.nodes[n],g,{(1,0,-1):10,(3,0,-1):30})
  self.assertEqual(d['indications'],['circular_red']);self.assertEqual(d['governs'],[30]);self.assertNotIn(10,d['governs'])
 def test_absent_is_absent(self):
  g=nx.MultiDiGraph();self.assertEqual(helper.augment_graph(g,{'head_states':[]})['added_nodes'],[]);self.assertEqual(len(g),0)
 def test_missing_lane_readback_fails(self):
  with self.assertRaisesRegex(ValueError,'cannot infer governance'):helper.augment_graph(nx.MultiDiGraph(),{'head_states':[{'actor_id':1,'state':'Off'}]})
 def test_dark_head_is_dark(self):
  g=nx.MultiDiGraph();n=helper.augment_graph(g,{'head_states':[{'actor_id':1,'state':'Off','affected_lanes':[[1,0,-1]]}]})['added_nodes'][0]
  self.assertEqual(device_record(n,g.nodes[n],g,{(1,0,-1):10})[1]['indications'],['dark'])
 def test_all2504_current_diagnostic_cases(self):
  import json,shutil,tempfile
  repo=OWN.parents[1];count=0
  sources=[]
  for manifest_path in sorted((repo/'work').glob('*__NRS-484B-250-4__*/execution-manifest.json')):
   manifest=json.loads(manifest_path.read_text())
   sources.extend((manifest_path.parent,entry) for entry in manifest['cases'])
  for folder,entry in sources:
   with self.subTest(case=entry['case_id']),tempfile.TemporaryDirectory(dir=repo/'.runtime-work/migration-inventory/tmp') as t:
    root=Path(t);bundle=json.loads((folder/entry['construction']).read_text());files={f['path']:f['content'] for f in bundle['files']}
    for name in ('config.json','scene.xodr'):(root/name).write_text(files[name])
    recipe=json.loads((repo/entry['fixture_recipe']).read_text())
    for item in recipe['additions']:
     if item['path'] in ('signal_context.json','interaction_history.jsonl'):shutil.copyfile(repo/item['source'],root/item['path'])
    (root/'fixture-provenance.json').write_text(json.dumps({'diagnostic_fixture':True}))
    cfg=json.loads((root/'config.json').read_text());before=json.loads((root/'signal_context.json').read_text());report=helper.diagnostic_enrich2504(root,cfg)
    rows=[json.loads(x) for x in (root/'interaction_history.jsonl').read_text().splitlines()]
    if cfg.get('installed_heads',True) is False:
     self.assertTrue(report['absent_preserved']);self.assertEqual(json.loads((root/'signal_context.json').read_text()),before)
    else:
     for row in rows:
      g=nx.MultiDiGraph();nodes=helper.augment_graph(g,row)['added_nodes'];self.assertEqual(len(nodes),4)
      for n in nodes:
       lanes=g.nodes[n]['observed_governs'];self.assertTrue(all(l[0]==int(g.nodes[n]['carla_id']) for l in lanes))
    count+=1
  self.assertEqual(count,16)
if __name__=='__main__':unittest.main()
