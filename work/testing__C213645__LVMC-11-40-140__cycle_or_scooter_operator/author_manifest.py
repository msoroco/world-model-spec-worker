"""Initialize exact driveway execution entries and measurement contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from driveway_case import CASES
from author_semantics import CHANNELS

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
AID=ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    disposition=plan['requirement_dispositions'][0]
    contract={'format':'worker-measurement-contract',
              'requirements':[{'disposition_index':0,'requirement':disposition['requirement'],
                               'source':disposition['source'],
                               'output_key':'driveway_stop_pedestrian_yield',
                               'method':'analyze','value_type':'object','kind':'measured',
                               'inputs':['driveway-history.jsonl','driveway-site.json',
                                         'video_frames.jsonl','trace.jsonl']}],
              'negative':{'remove':['driveway-site.json'],
                          'error_contains':'Missing required source: driveway-site.json'}}
    write(ROOT/'measurement-contract.json',contract)
    entries=[]
    for i,item in enumerate(CASES):
        cid=AID+'__'+item.case_id
        construction=ROOT/'construction.json' if i==0 else ROOT/'cases'/item.case_id/'construction.json'
        entries.append({'case_id':cid,'kind':'delivery',
                        'construction':str(construction.relative_to(ROOT)),
                        'construction_sha256':sha(construction),
                        'fixture_recipe':str((ROOT/('diagnostic-'+item.case_id+'-recipe.json')).relative_to(REPO)),
                        'measurement_contract':'measurement-contract.json',
                        'measurement_procedure':{'entrypoint':'analysis.py'},
                        'source_gate':'reviewed original district, driveway, sidewalk and pedestrian source packet absent',
                        'acquisition':{name:{'entrypoint':'analysis.py',
                                             'method':'original Native source-bound cycle, edge, pedestrian and yield readback',
                                             'evidence':'channel-'+name+'.jsonl'} for name in CHANNELS},
                        'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                          'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
                        'candidate_risk':{'status':'none',
                                          'reason':'Reviewed driveway geometry and cycle/pedestrian route are source gated; no distinct CPU-grounded fallback trigger is established.'},
                        'candidates':[]})
    write(ROOT/'execution-manifest.json',{'format':'worker-execution-manifest',
                                           'assignment_id':AID,'status':'source_gated_draft',
                                           'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
                                           'cases':entries})


if __name__=='__main__':
    main()
