"""Exercise one selected reference construction through current CPU runtime."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MANIFEST=HERE/'update016-selected-reference-probe-manifest.json'
CASE=HERE.name+'__reference';LIBRARY=ROOT/'runtime/pipeline/library'
VALIDATOR=ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
RUN=ROOT/'.runtime-work/c110919-update016-selected-reference-primary-v2'
PROOFS=HERE/'update016-selected-reference-primary-proofs';PROOFS.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args,name):
 run=subprocess.run([sys.executable,str(ROOT/'runtime.py'),*args],cwd=ROOT,text=True,capture_output=True)
 log=PROOFS/(name+'.log');log.write_text(run.stdout+run.stderr)
 if run.returncode:raise ValueError(name+' failed: '+log.read_text())
 return json.loads(run.stdout),log
entry=json.loads(MANIFEST.read_text())['cases'][0];assert entry['case_id']==CASE and entry['id']=='primary' and entry['kind']=='delivery'
offline,offline_log=command(['offline','--manifest',str(MANIFEST),'--case',CASE,'--candidate','primary','--output',str(RUN/'offline'),'--python',sys.executable],'offline')
common=['--manifest',str(MANIFEST),'--case',CASE,'--candidate','primary','--library',str(LIBRARY),'--validator',str(VALIDATOR)]
compat,compat_log=command(['compatibility',*common,'--output',str(RUN/'compatibility')],'compatibility')
assert compat['passed'] is True and compat['candidate_id']=='primary' and compat['construction_sha256']==entry['construction_sha256'] and compat['negative_removed']=='road_geometry.json'
saved,saved_log=command(['process-saved',*[arg for arg in common if arg not in ('--candidate','primary')],
                         '--attempt',str(RUN/'compatibility'),'--output',str(RUN/'saved')],'process-saved')
assert saved['passed'] is True and saved['originals_preserved'] is True and saved['missing_evidence'] is False and saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
proof={'format':'c110919-selected-reference-primary-cpu-v1','case_id':CASE,'manifest_sha256':sha(MANIFEST),'construction_sha256':entry['construction_sha256'],'offline_log_sha256':sha(offline_log),'compatibility_log_sha256':sha(compat_log),'process_saved_log_sha256':sha(saved_log),'compatibility_receipt_sha256':sha(RUN/'compatibility/compatibility.json'),'saved_receipt_sha256':sha(RUN/'saved/v0001/processing.json'),'selected_in_probe_only':True,'original_native_accepted':False}
out=PROOFS/'proof.json';out.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'primary_offline':True,'compatibility_positive_negative':True,'process_saved':True,'proof_sha256':sha(out),'original_native_accepted':False}))
