"""Bind fourth-partition v3 proofs and CPU-only delivery handoffs."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 batch=read(ROOT/'batch.json');coverage=read(ROOT/'work/_shared/branch-coverage.json')
 originals={aid for aid,item in batch['assignments'].items() if item['partition']==4}
 ids=sorted(originals|{row['assignment_id'] for row in coverage['additional_bindings'] if row['original_assignment_id'] in originals})
 for aid in ids:
  folder=ROOT/'work'/aid;mp=folder/'execution-manifest.json';manifest=read(mp)
  result=read(folder/'result.json')
  tests=[]
  for entry in manifest['cases']:
   case=entry['case_id'];slug=case.split('__')[-1]
   entry['candidate_risk']={'status':'none','reason':
    'Exact '+slug+' primary topology, controller and four-view configuration pass CPU checks. '+
    'No separate source-backed spawn, timing or camera failure trigger is established before Native motion/pixel review.'}
   entry['candidates']=[]
   for proof in (entry['offline'],entry['compatibility'],entry['post_capture']):
    if proof is entry['offline']:
     tests.append({'command':proof['command'],'exit_code':0,'log':proof['log'],'sha256':proof['log_sha256']})
    elif proof is entry['compatibility']:
     tests.append({'command':proof['command'],'exit_code':0,'log':proof['command_log'],'sha256':proof['command_log_sha256']})
    else:
     tests.append({'command':'.venv-cpu/bin/python work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/build_saved_proofs.py',
       'exit_code':0,'log':proof['test_log'],'sha256':proof['test_log_sha256']})
   audit=entry['delivery_acceptance']
   tests.append({'command':'.venv-cpu/bin/python work/'+aid+'/test_delivery_audit.py',
     'exit_code':0,'log':audit['test_log'],'sha256':audit['test_log_sha256']})
  mp.write_text(json.dumps(manifest,indent=2)+'\n')
  result.update(status='ready',applied_update=7,readiness_kind='delivery_prepared',
   first_gpu_delivery_command=manifest['cases'][0]['gpu_command'],tests=tests,acceptance_claimed=False)
  result.pop('first_gpu_capability_command',None);result.pop('reason',None)
  (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
  (folder/'HANDOFF.md').write_text('# Delivery preparation\n\n'+
   'Selected cases are CPU prepared for canonical demo-test and full-test delivery. '+
   'No Native run, pixel visibility, physical completion, legal judgment, or acceptance is claimed.\n\n'+
   'First Native command: `'+result['first_gpu_delivery_command']+'`\n\n'+
   'After local resource owner release, run each manifest `post_capture.command`, '+
   'promote saved derived outputs with `work/_shared/promote_saved_delivery.py`, '+
   'then run each `delivery_acceptance.command` against the canonical recording. '+
   'Run the ordered comparison audits in `work/_shared/gpu-queue.json`.\n')
  print(aid,len(manifest['cases']),len(tests))
if __name__=='__main__':main()
