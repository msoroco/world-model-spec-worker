"""Bind exact diagnostic constructions to selected delivery planning artifacts."""
from __future__ import annotations

import json
from pathlib import Path

from overpass_source import CASES, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW = 'LVMC-11-30-060-B'
REQUIREMENTS = (
    ('Pedestrian roadway crossing at a point with a provided overhead pedestrian crossing',
     'LVMC 11.30.060(B)', 'provided_overhead_crossing',
     'measure_provided_overhead_crossing', 'object',
     ['candidate-overpass.xodr','reviewed-site.json','reviewed-site-source.txt']),
    ('Observed pedestrian entry and exit relative to all vehicles upon the roadway',
     'LVMC 11.30.060(B)', 'crossing_order', 'measure_crossing_order', 'object',
     ['body-history.jsonl','video_frames.jsonl']),
    ('All Native vehicle identities and reviewed roadway bounds',
     'LVMC 11.30.060(B)', 'roadway_vehicle_inventory',
     'measure_roadway_vehicle_inventory', 'object',
     ['body-history.jsonl','reviewed-site.json']),
    ('Designated-place prohibition exception context',
     'LVMC 11.30.060(C); LVMC 11.30.070', 'designated_place_prohibition',
     'measure_designated_place', 'boolean',
     ['reviewed-site.json','municipal-designation-source.txt']),
)


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    from hashlib import sha256
    draft=json.loads((ROOT/'draft-offline-manifest.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    ids=[ASSIGNMENT+'__'+variant for variant in CASES]
    plan['requirement_dispositions']=[{
        'requirement':requirement,'source':source,'status':'selected_required',
        'case_ids':ids,'evidence_or_gap':'Selected source-bound measurement; original Native review pending'
    } for requirement,source,*_ in REQUIREMENTS]
    plan['source_observation_mapping']={}
    plan['observations']=[{'name':name,'mandatory':True,
                           'source':'source-hashed original acquisition and reviewed site packet'}
                          for _,_,name,*_ in REQUIREMENTS]
    plan['camera_plan']={'profile':'overview1080-capability',
       'duration_s':45.0,'composition':'synchronized_four_view_primary',
       'coverage':[{'view':name,'subject':'pedestrian, roadway vehicles and overhead crossing',
                    'interval':'full 45 second crossing'}
                   for name in ('overview','approach','reference_corner','driver_reference')]}
    write(ROOT/'case-plan.json',plan)
    semantic={'cell_id':'C188132','actor':'pedestrian','status':'proposed',
              'sweeps_expanded':True,'sweep_specs':[],'cases':[]}
    base=draft['cases'][0]
    description=json.loads((ROOT/base['construction']).read_text())['recording_description']
    semantic['cases'].append({'case_id':ASSIGNMENT+'__semantic_baseline',
        'target_law_id':LAW,'target_type':'baseline',
        'rationale':'Shared semantic overpass route baseline; no extra recording.',
        'variable_assignments':{},'deliberate_differences':[],
        'unresolved_judgment_calls':['yield the right-of-way'],
        'recording_description':description})
    entries=[]
    for variant, draft_case in zip(CASES,draft['cases']):
        cid=ASSIGNMENT+'__'+variant
        semantic['cases'].append({'case_id':cid,'target_law_id':LAW,
            'target_type':'controlled_attempt' if variant!='designated_prohibition' else 'exception_probe',
            'rationale':'Exact reviewed overpass crossing source comparison',
            'variable_assignments':{},
            'deliberate_differences':['requested_hold_until_vehicle_passes' if variant=='yield_before_vehicle'
                                      else 'designated_prohibition' if variant=='designated_prohibition'
                                      else 'pedestrian entry timing'],
            'unresolved_judgment_calls':['yield the right-of-way'],
            'recording_description':description})
        contract={'format':'worker-measurement-contract','case_id':cid,
            'requirements':[{'disposition_index':index,'requirement':requirement,
                'source':source,'output_key':key,'method':method,'value_type':type_,
                'kind':'measured' if key in ('crossing_order','roadway_vehicle_inventory')
                       else 'sourced_context','inputs':inputs}
                for index,(requirement,source,key,method,type_,inputs) in enumerate(REQUIREMENTS)],
            'negative':{'remove':['body-history.jsonl'],
                        'error_contains':'Missing required source: body-history.jsonl'},
            'scope':'Original source measurement, not legal or physical acceptance'}
        contract_path=ROOT/('measurement-contract-'+variant+'.json')
        write(contract_path,contract)
        entries.append({'case_id':cid,'construction':draft_case['construction'],
          'construction_sha256':draft_case['construction_sha256'],
          'kind':'delivery','candidate_risk':draft_case['candidate_risk'],
          'candidates':[],
          'measurement_contract':contract_path.name,
          'measurement_procedure':{'entrypoint':'analysis.py'},
          'fixture_recipe':'work/'+ASSIGNMENT+'/fixture-recipe-'+variant+'.json',
          'native_handoff':{'python_env_var':'CARLA_PYTHON',
                            'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT',
                            'site_root_env_var':'C188132_REVIEWED_SITE_PACKET'}})
    write(ROOT/'proposals/cases.json',semantic)
    manifest_sha=sha(REPO/'runtime/SOURCE-MANIFEST.json')
    write(ROOT/'execution-manifest.json',{'format':'worker-execution-manifest',
        'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':manifest_sha,'cases':entries})


if __name__=='__main__':main()
