"""Bind five exact emergency caution constructions and source-gated contracts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SOURCES=('emergency-review.json','road.xodr','video_frames.jsonl','emergency-native.jsonl',
         'lamp-pixel-review.json','signal-pixel-review.json','trace.jsonl',
         *(f'source_context/{x}.txt' for x in ('vehicle_authorization','flashing_equipment',
           'flashing_qualification','lamp_pixels','lane_topology','roadway_conditions',
           'traffic_conditions','weather_conditions','officer_direction','hand_signal_pixels')),
         'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value): path.write_text(json.dumps(value,indent=2).rstrip()+'\n')
def main():
    plan=json.loads((HERE/'case-plan.json').read_text())
    entries=[]
    for i in range(1,6):
        suffix=f'probe_0{i}'; case=HERE.name+'__'+suffix
        directory=HERE/'cases'/suffix
        contract={'format':'worker-measurement-contract','case_id':case,
          'requirements':[{'disposition_index':j,'requirement':'NRS-484B-267-2b',
             'source':'NRS 484B.267(2)(b); with 484B.267(4)','kind':'measured',
             'method':'measure_'+('moving_approach','regulatory_role','visible_preparation','officer_direction','qualitative_caution')[j],
             'output_key':('moving_approach','regulatory_role','visible_preparation','officer_direction','qualitative_caution')[j],'value_type':'object',
             'inputs':list(SOURCES)} for j,x in enumerate(plan['requirement_dispositions'])
             if case in x['case_ids']],
          'negative':{'remove':['emergency-native.jsonl'],
                      'error_contains':'Missing required source: emergency-native.jsonl'}}
        put(directory/'measurement-contract.json',contract)
        construction=directory/'construction.json'
        entries.append({'case_id':case,'kind':'delivery',
          'construction':construction.relative_to(HERE).as_posix(),
          'construction_sha256':sha(construction),
          'candidate_risk':{'status':'none','reason':'The source-preserving fixed two-lane approach has no justified alternate that resolves original authorization, lamp, hand-signal, officer or caution review; the primary camera and approach plan is CPU checked.'},
          'candidates':[],'delivery_readiness':'cpu_construction_original_capture_pending',
          'measurement_contract':(directory/'measurement-contract.json').relative_to(HERE).as_posix(),
          'measurement_procedure':{'entrypoint':'finalize.py'},
          'fixture_recipe':'work/'+HERE.name+'/cases/'+suffix+'/fixture-recipe.json',
          'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
          'acquisition':{item['name']:{'entrypoint':'runner.py',
              'method':'Original Native actor/lane/frame and source-gated lamp, role, visibility and officer review',
              'evidence':list(SOURCES)} for item in plan['observations']},
          'offline':{},'compatibility':{},'negative':{},'post_capture':{},
          'physical_preparation':{},'delivery_acceptance':{}})
    put(HERE/'execution-manifest.json',{'format':'worker-execution-manifest','assignment_id':HERE.name,
       'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
       'status':'partial','cases':entries})
    print('Built',len(entries),'exact case manifests and measurement contracts')
if __name__=='__main__': main()
