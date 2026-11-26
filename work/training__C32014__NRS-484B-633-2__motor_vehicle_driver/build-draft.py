"""Build bridge structure-speed CPU Native draft on pinned runtime."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASES={
    'probe_01': ('below_posted_structure_speed',9.0),
    'probe_02': ('above_posted_structure_speed',13.0),
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    manifest_cases=[]
    for suffix,(label,target_mps) in CASES.items():
      case=HERE.name+'__'+suffix
      variants=[]
      for candidate,starting_x in (('primary',-70.0),('fallback1',-60.0)):
       config={'case_id':case,'selected_case_id':case,
      'supported_case_ids':[HERE.name+'__'+key for key in CASES],
      'candidate_id':candidate,'initial_spawn_x_m':starting_x,
      'law_id':'NRS-484B-633-2','cell_id':'C32014',
      'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,'required_atoms':[],
      'source_packets':[],'case':{'case_id':case},
      'cameras':[{'name':name,'width':1920 if name == 'overview' else 1280,
                 'height':1080 if name == 'overview' else 720,
                 'fov_deg':85,
                 'pose_strategy':('attached ego driver reference' if name == 'driver_reference'
                                  else 'fixed surveyed bridge view')} for name in
        ('overview','approach','reference_corner','driver_reference')],
      'recording_description':{'channels':[
        {'name':'original_velocity_position','unit':'structured','sampling_rate_hz':20,
         'method':'Native post-tick actor velocity and transform','time_window':'600 frames',
         'reference_frame':'bridge OpenDRIVE','uncertainty':'50 ms sampling'},
        {'name':'structure_sign_survey','unit':'structured','sampling_rate_hz':20,
         'method':'Native map/sign/elevation readback','time_window':'600 frames',
         'reference_frame':'bridge road 1','uncertainty':'physical pixels unverified'}],
        'context_inputs':[],
        'limitations':['Department structural-safety investigation/determination absent',
                       'Original sign pixels and bridge mesh unverified']},
      'status':'partial_cpu_draft','requested_speed_mps':target_mps}
       config['case']['recording_description']=config['recording_description']
       files=[{'path':name,'content':(HERE/'native'/name).read_text()}
        for name in ('runner.py','geometry.py','measure.py','finalize.py','tests/test_native.py')]
       files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
       proposal={'case_id':case,'law_id':config['law_id'],'cell_id':config['cell_id'],
      'actor':config['actor'],'entrypoint':'runner.py','files':files,
      'recording_description':config['recording_description'],
      'measurement_plan':{'entrypoint':'finalize.py',
        'required_sources':['bridge-speed-history.jsonl','bridge-context.json'],
        'status':'source_bound_cpu_draft'},
      'static_checks':['300m road with elevated 100m bridge deck',
        'two 100-foot advance sign metadata records','four cameras, 600 frames'],
      'termination_rules':['600 original frames','restore world and destroy owned actors'],
      'mechanisms':[f'{target_mps}m/s request over surveyed structure',
        f'spawn at {starting_x} m before the surveyed bridge',
        'measure actual post-tick speed only on elevated structure'],
      'status':'partial_native_execution_cpu_checked_physical_unverified'}
       path=HERE/'draft-bridge'/label/candidate/'construction.json'
       path.parent.mkdir(parents=True,exist_ok=True)
       path.write_text(json.dumps(proposal,indent=2)+'\n')
       variants.append((candidate,path))
      primary=variants[0][1];fallback=variants[1][1]
      manifest_cases.append({'case_id':case,'kind':'delivery',
        'construction':str(primary.relative_to(HERE)),'construction_sha256':sha(primary),
        'fixture_recipe':str((HERE/'diagnostic'/suffix/'fixture-recipe.json').relative_to(ROOT)),
        'measurement_contract':f'diagnostic/{suffix}/measurement-contract.json',
        'candidate_risk':{'status':'physical',
          'reason':'Native bridge mesh, sign pixels and actual speed require inspection'},
        'candidates':[{'id':'fallback1','construction':str(fallback.relative_to(HERE)),
          'construction_sha256':sha(fallback),
          'trigger':{'source':'original Native trajectory and camera audit',
                     'metric':'first stable on-deck frame plus legible near sign pixels',
                     'failure_condition':'primary has no stable on-deck frame or sign face leaves all views'},
          'changed_knobs':['start 10 m closer to bridge; preserve requested speed and observation contract']}],
        'measurement_procedure':{'entrypoint':'finalize.py'},
        'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':HERE.name,
      'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
      'status':'partial','cases':manifest_cases}
    (HERE/'draft-bridge-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'case_ids':[entry['case_id'] for entry in manifest_cases],
      'construction_sha256':[entry['construction_sha256'] for entry in manifest_cases],
      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))
if __name__=='__main__':main()
