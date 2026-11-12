"""Check nine selected audit branches on retained, source-bound CPU attempts."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
from source_join_audit import read,require,sha
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];AUDITOR=HERE/'delivery_audit.py'
def run(case,negative=False):
 manifest=read(HERE/'execution-manifest.json');entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
 require(entry is not None and entry['kind']=='delivery','Delivery case is not selected')
 suffix=case.removeprefix(HERE.name+'__')
 if suffix in ('reference','contrast'):
  source_manifest=HERE/'draft-execution-manifest.json';run_root=ROOT/'.runtime-work/c110454-update040-intersection-draft';proof_root=HERE/'update040-intersection-draft-proofs'
 else:
  source_manifest=HERE/'update040-pre-nine-case-manifest.json';run_root=ROOT/'.runtime-work/c110454-update038-seven-selected';proof_root=HERE/'update038-selected-proofs'
 proof=read(proof_root/suffix/'primary/proof.json');attempt=run_root/suffix/'primary/compatibility';saved=proof_root/suffix/'primary/process-saved.log'
 require(proof['manifest_sha256']==sha(source_manifest) and proof['construction_sha256']==entry['construction_sha256'] and proof['process_saved_log_sha256']==sha(saved),'Retained source proof changed')
 require(read(attempt/'candidate-selection.json')['manifest_sha256']==sha(source_manifest),'Retained source selection changed')
 with tempfile.TemporaryDirectory(prefix='c110454-nine-delivery-') as temp:
  out=Path(temp)/'audit.json';construction='0'*64 if negative else entry['construction_sha256']
  command=[sys.executable,str(AUDITOR),'--case',case,'--candidate','primary','--construction-sha256',construction,'--attempt',str(attempt),'--processing',str(saved),'--output',str(out),'--diagnostic']
  run=subprocess.run(command,cwd=ROOT,text=True,capture_output=True);content=run.stdout+run.stderr
  if negative:
   require(run.returncode!=0 and 'Delivery construction differs from selected manifest' in content and not out.exists(),'Wrong construction accepted')
   print(content,end='');return
  require(run.returncode==0 and out.is_file(),'Diagnostic delivery auditor failed: '+content)
  receipt=read(out);require(receipt['source_shaped_unit_test'] is True and receipt['passed'] is False and not any(receipt['checks'].values()) and receipt['physical_or_legal_acceptance_claimed'] is False,'CPU fixture promoted to acceptance')
  print(json.dumps({'case_id':case,'auditor_sha256':sha(AUDITOR),'source_shape_passed':True,'delivery_accepted':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--negative',action='store_true');a=p.parse_args();run(a.case,a.negative)
 if a.negative:sys.exit(1)
