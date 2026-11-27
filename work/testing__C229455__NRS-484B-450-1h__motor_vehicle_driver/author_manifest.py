"""Create twelve exact delivery manifest entries before proof binding."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from safety_zone import CASES
from author_plan import CHANNELS

ROOT=Path(__file__).resolve().parent
AID=ROOT.name

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def main():
    path=ROOT/'execution-manifest.json'
    if path.exists():
        old=json.loads(path.read_text())
        if any(e.get('compatibility') or e.get('physical_preparation') for e in old.get('cases',[])):
            raise ValueError('Do not overwrite proof-bearing manifest')
    entries=[]
    for i,c in enumerate(CASES):
        cid=AID+'__'+c.case_id
        construction='construction.json' if i==0 else 'cases/'+c.case_id+'/construction.json'
        entries.append({'case_id':cid,'kind':'delivery','construction':construction,
          'construction_sha256':sha(ROOT/construction),
          'fixture_recipe':'work/'+AID+'/diagnostic-'+c.case_id+'-recipe.json',
          'measurement_contract':'measurement-contract.json',
          'measurement_procedure':{'entrypoint':'analysis.py'},
          'source_gate':'reviewed original highway, official pedestrian-exclusive zone, visible marking, adjacent curb and authority packet required',
          'acquisition':{name:{'entrypoint':'analysis.py',
             'method':'original Native frame source and saved-only extraction',
             'evidence':'channel-'+name+'.jsonl'} for name in CHANNELS},
          'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                            'port_env_var':'CARLA_PORT'},
          'candidate_risk':{'status':'physical',
             'reason':'Tight zone-curb approach or end-station placement may fail to reach stable terminal body position with full marker visibility in Native capture.'},
          'candidates':[]})
    write(path,{'format':'worker-execution-manifest','assignment_id':AID,
      'status':'source_gated_draft','runtime_manifest_sha256':sha(ROOT.parents[1]/'runtime/SOURCE-MANIFEST.json'),
      'cases':entries})
if __name__=='__main__':main()
