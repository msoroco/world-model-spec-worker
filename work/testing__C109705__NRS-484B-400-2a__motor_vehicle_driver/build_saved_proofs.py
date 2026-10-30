"""Rerun partition-1 saved-only diagnostic processing against pinned v3."""
import hashlib,json,sys,shutil,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('runtime_v3_launcher',ROOT/'work/_shared/runtime-v3.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
effective=launcher.runtime()
sys.path.insert(0,str(effective/'scenario_pipeline'))
from worker_exchange.saved_processing import run

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
batch=json.loads((ROOT/'batch.json').read_text())
for aid,meta in batch['assignments'].items():
 if meta['partition']!=1:continue
 folder=ROOT/'work'/aid;path=folder/'execution-manifest.json'
 manifest=json.loads(path.read_text())
 for entry in manifest['cases']:
  case=entry['case_id'];slug=case.split('__')[-1]
  attempt=ROOT/'.runtime-work'/aid/('delivery-v3-'+slug)/'compat'
  output=ROOT/'.runtime-work'/aid/('delivery-v3-'+slug)/'saved'
  if output.exists():shutil.rmtree(output)
  selection=attempt/'candidate-selection.json'
  if selection.exists():selection.unlink() # Diagnostic primary, no fallback.
  try:
   result=run(path,case,attempt,output,effective/'library',
    ROOT/'.runtime-work/decoder-v3/.lake/build/bin/adapterCheck')
   assert result['originals_preserved'] and not result['missing_evidence'] and result['final_video_checks']
  except Exception as error:
   print('SAVED FAIL',case,type(error).__name__,error,flush=True);raise
  log=folder/'receipts'/('delivery-v3-saved-'+slug+'.log')
  log.write_text('CPU diagnostic fixture only; no physical acceptance.\n'+json.dumps(result,indent=2)+'\n')
  entry['post_capture']['test_log']=str(log.relative_to(folder))
  entry['post_capture']['test_log_sha256']=digest(log)
  entry['post_capture']['test_exit_code']=0
  print('SAVED PASS',case,flush=True)
 path.write_text(json.dumps(manifest,indent=2)+'\n')
