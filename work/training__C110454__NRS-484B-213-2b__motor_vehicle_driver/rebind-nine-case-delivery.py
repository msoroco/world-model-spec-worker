"""Bind all nine diagnostic delivery audit receipts to current canonical entries."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];manifest_path=HERE/'execution-manifest.json';manifest=json.loads(manifest_path.read_text());script=HERE/'prove-nine-case-delivery-historical.py';auditor=HERE/'delivery_audit.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
template=next(e['delivery_acceptance'] for e in manifest['cases'] if 'delivery_acceptance' in e)
assert len(manifest['cases'])==9
for entry in manifest['cases']:
 suffix=entry['case_id'].rsplit('__',1)[-1];folder=HERE/'update040-nine-delivery-case-proofs'/suffix;folder.mkdir(parents=True,exist_ok=True)
 audit=entry.setdefault('delivery_acceptance',dict(template));audit['case_id']=entry['case_id'];audit['script']='delivery_audit.py';audit['script_sha256']=sha(auditor)
 for negative,label in [(False,'positive'),(True,'negative')]:
  cmd=[sys.executable,str(script),'--case',entry['case_id']]+(['--negative'] if negative else [])
  run=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True);log=folder/(label+'.log');log.write_text(run.stdout+run.stderr)
  if negative:
   assert run.returncode==1 and 'Delivery construction differs from selected manifest' in log.read_text(),(suffix,label,log.read_text())
   audit.update(negative_command=' '.join(cmd),negative_exit_code=1,negative_expected_error='Delivery construction differs from selected manifest',negative_log=str(log.relative_to(HERE)),negative_log_sha256=sha(log))
  else:
   assert run.returncode==0 and '"source_shape_passed": true' in log.read_text(),(suffix,label,log.read_text())
   audit.update(command=' '.join(cmd),test_exit_code=0,test_log=str(log.relative_to(HERE)),test_log_sha256=sha(log))
 print(json.dumps({'case':suffix,'positive':True,'negative_rejected':True}),flush=True)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':9,'manifest_sha256':sha(manifest_path),'original_native_accepted':False}))
