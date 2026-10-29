"""Exact-case update002 CPU revalidation on the immutable repaired runtime."""
import argparse,contextlib,json,pathlib,shutil,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'work/_shared'))
from update002_tools import read,write,sha
import runtime002

def main():
 p=argparse.ArgumentParser();p.add_argument('--assignment',required=True);p.add_argument('--case');p.add_argument('--phase',choices=['software','physical','all'],default='all');a=p.parse_args()
 runtime=runtime002.prepare_runtime();runtime002.activate_runtime(ROOT,runtime)
 from worker_exchange.runtime_cli import offline
 from worker_exchange.package_compatibility import run_recipe
 from worker_exchange.saved_processing import run
 from prove_physical002 import prove_entry
 folder=ROOT/'work'/a.assignment;path=folder/'execution-manifest.json';m=read(path);receipts=folder/'receipts';base=ROOT/'.runtime-work'/a.assignment/('update002-'+uuid.uuid4().hex[:10]);base.mkdir(parents=True)
 assert m['runtime_manifest_sha256']==sha(runtime/'SOURCE-MANIFEST.json')
 library=ROOT/'runtime/main-pipeline-v1/library';validator=ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck'
 for i,e in enumerate(m['cases']):
  if a.case and e['case_id']!=a.case:continue
  cid=e['case_id'];suffix=cid.rsplit('__',1)[-1]
  if a.phase in ('software','all'):
   destination=base/('offline-'+str(i));log=receipts/('offcheck002-'+suffix+'.log')
   command=f'python3.11 work/_shared/runtime002.py runtime.py offline --manifest work/{a.assignment}/execution-manifest.json --case {cid} --output {destination.relative_to(ROOT)}'
   with log.open('w') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
    print('COMMAND',command);outcome=offline(path,cid,destination,sys.executable);print(read_log(destination/'offline.log'));print(json.dumps(outcome))
   e['offline']={'command':command,'exit_code':0,'log':str(log.relative_to(folder)),'log_sha256':sha(log),'construction_sha256':e['construction_sha256']};write(path,m)
   out=base/('compat-'+str(i));log=receipts/('compatcheck002-'+suffix+'.log')
   with log.open('w') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
    receipt=run_recipe(path,cid,out,library,validator);print(json.dumps(receipt,indent=2))
   for source,name in [('compatibility.json','compatcheck002-'+suffix+'.json'),('compatibility-analysis.log','analysis002-'+suffix+'.log'),('negative-analysis.log','negative002-'+suffix+'.log')]:shutil.copyfile(out/source,receipts/name)
   e['compatibility']={'receipt':'receipts/compatcheck002-'+suffix+'.json','sha256':sha(receipts/('compatcheck002-'+suffix+'.json')),'log':'receipts/analysis002-'+suffix+'.log'};e['negative']={'log':'receipts/negative002-'+suffix+'.log'}
   e['gpu_command']=f'python3.11 work/_shared/runtime002.py runtime.py capture --manifest work/{a.assignment}/execution-manifest.json --case {cid} --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/{a.assignment}/native002-{i}'
   e['owner_release_command']=f'python3.11 work/_shared/runtime002.py runtime.py owner-released --attempt .runtime-work/{a.assignment}/native002-{i} --receipt .runtime-work/{a.assignment}/owner002-{i}.json --acknowledge-owner-released'
   command=f'python3.11 work/_shared/runtime002.py runtime.py process-saved --manifest work/{a.assignment}/execution-manifest.json --case {cid} --attempt .runtime-work/{a.assignment}/native002-{i} --output .runtime-work/{a.assignment}/processed002-{i} --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR" --owner-release-receipt .runtime-work/{a.assignment}/owner002-{i}.json'
   log=receipts/('saved002-'+suffix+'.log')
   with log.open('w') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
    print('Saved original result retained before selected reanalysis:',sha(out/'result.json'));result=run(path,cid,out,base/('saved-'+str(i)),library,validator);assert result['originals_preserved'] and result['final_video_checks'];print(json.dumps(result,indent=2))
   e['post_capture']={'recorded_only':True,'command':command,'feedback_command':f'cat .runtime-work/{a.assignment}/processed002-{i}/v*/feedback.json','test_log':str(log.relative_to(folder)),'test_log_sha256':sha(log),'test_exit_code':0,'output_layout':'fresh vNNNN/analysis plus processing.json; originals never overwritten','owner_release_required':True}
   write(path,m)
  if a.phase in ('physical','all'):
   e=prove_entry(folder,e,runtime);m['cases'][i]=e;write(path,m)
  print(cid,a.phase,'PASS',flush=True)
 result=read(folder/'result.json');result['applied_update']=2
 if all(e.get('physical_preparation') and e.get('compatibility') and e.get('offline') and e.get('post_capture') for e in m['cases']):
  result.update(status='ready',readiness_kind='capability',first_gpu_capability_command=m['cases'][0]['gpu_command']);result.pop('reason',None)
 result['tests']=[{'command':e['offline']['command'],'exit_code':0,'log':e['offline']['log'],'sha256':e['offline']['log_sha256']} for e in m['cases'] if e.get('offline')]
 result['acceptance_claimed']=False;write(folder/'result.json',result)
 (folder/'HANDOFF.md').write_text('Update002: capture-only Native execution; operator must release actual resource ownership before acknowledging owner release. No resource operation is performed by this portable code.\n\nSaved processing always selects current analysis, preserves original acquisition/results, and writes a fresh vNNNN directory. A retained prior capture may be processed without replay after owner release. Native physical/legal acceptance remains unclaimed.\n\n'+'\n\n'.join(e.get('gpu_command','')+'\n\nAfter actual operator resource release:\n\n'+e.get('owner_release_command','')+'\n\n'+e.get('post_capture',{}).get('command','') for e in m['cases']))

def read_log(p):return pathlib.Path(p).read_text()
if __name__=='__main__':main()
