"""Rerun partition-4 saved-only diagnostic processing against pinned v3."""
import hashlib,json,sys,shutil,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import importlib.util
spec=importlib.util.spec_from_file_location('worker_v3_runtime',ROOT/'work/_shared/runtime-v3.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sys.path.insert(0,str(module.runtime()/'scenario_pipeline'))
from worker_exchange.saved_processing import run

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
batch=json.loads((ROOT/'batch.json').read_text())
coverage=json.loads((ROOT/'work/_shared/branch-coverage.json').read_text())
originals={aid for aid,meta in batch['assignments'].items() if meta['partition']==4}
ids=sorted(originals | {row['assignment_id'] for row in coverage['additional_bindings'] if row['original_assignment_id'] in originals})
for aid in ids:
 if os.environ.get('DELIVERY_ONLY') and aid not in os.environ['DELIVERY_ONLY'].split(','):continue
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
   result=run(path,case,attempt,output,ROOT/'runtime/main-pipeline-v3/library',
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
