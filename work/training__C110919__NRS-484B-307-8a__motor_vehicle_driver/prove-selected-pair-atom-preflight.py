"""Check eight exact selected-probe Core requirements against pinned adapter paths."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'runtime/pipeline'),str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.preparation import runtime_for
from scenario_pipeline.worker_exchange.atom_preflight import check_required_atoms
runtime=runtime_for(ROOT,json.loads((ROOT/'batch.json').read_text()))
m=json.loads((HERE/'update017-selected-pair-probe-manifest.json').read_text());count=0
for e in m['cases']:
 for c in (e,*e['candidates']):
  construction=json.loads((HERE/c['construction']).read_text());config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
  check_required_atoms(runtime,config.get('required_atoms',[]),config.get('source_packets',[]),config)
  count+=1
assert count==8
print(json.dumps({'candidates':8,'core_atom_paths_passed':True}))
