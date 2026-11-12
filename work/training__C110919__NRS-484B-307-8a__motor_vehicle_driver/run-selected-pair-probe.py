"""Fresh pinned offline, compatibility and saved path for eight selected-probe bundles."""
import concurrent.futures,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MANIFEST=HERE/'update017-selected-pair-probe-manifest.json'
LIBRARY=ROOT/'runtime/pipeline/library';VALIDATOR=ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
RUN_ROOT=ROOT/'.runtime-work/c110919-update017-selected-pair-probe';PROOFS=HERE/'update017-selected-pair-proofs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(args,log):
 run=subprocess.run([sys.executable,str(ROOT/'runtime.py'),*args],cwd=ROOT,text=True,capture_output=True)
 log.write_text(run.stdout+run.stderr)
 if run.returncode:raise ValueError('CPU command failed: '+str(log)+' '+log.read_text()[-2000:])
 return json.loads(run.stdout)
def task(entry,candidate):
 suffix=entry['case_id'].rsplit('__',1)[-1];ident=candidate['id'];case=entry['case_id'];folder=PROOFS/suffix/ident;folder.mkdir(parents=True,exist_ok=True)
 run=RUN_ROOT/suffix/ident;common=['--manifest',str(MANIFEST),'--case',case]
 offline=command(['offline',*common,'--candidate',ident,'--output',str(run/'offline'),'--python',sys.executable],folder/'offline.log')
 args=[*common,'--candidate',ident,'--library',str(LIBRARY),'--validator',str(VALIDATOR)]
 compat=command(['compatibility',*args,'--output',str(run/'compatibility')],folder/'compatibility.log')
 if not (compat['passed'] is True and compat['case_id']==case and compat['candidate_id']==ident and compat['construction_sha256']==candidate['construction_sha256'] and compat['negative_removed']=='road_geometry.json'):
  raise ValueError('Selected-probe compatibility identity or negative differs')
 saved=command(['process-saved',*common,'--library',str(LIBRARY),'--validator',str(VALIDATOR),'--attempt',str(run/'compatibility'),'--output',str(run/'saved')],folder/'process-saved.log')
 if not (saved['passed'] is True and saved['case_id']==case and saved['candidate_id']==ident and saved['originals_preserved'] is True and saved['missing_evidence'] is False and saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False):
  raise ValueError('Selected-probe saved receipt differs')
 proof={'format':'c110919-selected-pair-candidate-cpu-v1','case_id':case,'candidate_id':ident,'manifest_sha256':sha(MANIFEST),'construction_sha256':candidate['construction_sha256'],'offline_log_sha256':sha(folder/'offline.log'),'compatibility_log_sha256':sha(folder/'compatibility.log'),'process_saved_log_sha256':sha(folder/'process-saved.log'),'compatibility_receipt_sha256':sha(run/'compatibility/compatibility.json'),'saved_receipt_sha256':sha(run/'saved/v0001/processing.json'),'original_native_accepted':False}
 path=folder/'proof.json';path.write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({'case':suffix,'candidate':ident,'passed':True}),flush=True)
 return {'case_id':case,'candidate_id':ident,'proof':str(path.relative_to(HERE)),'sha256':sha(path)}
def main():
 manifest=json.loads(MANIFEST.read_text());entries=manifest['cases'];assert len(entries)==2 and all(e['kind']=='delivery' and e['id']=='primary' and len(e['candidates'])==3 for e in entries)
 tasks=[(e,c) for e in entries for c in (e,*e['candidates'])]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  futures=[pool.submit(task,e,c) for e,c in tasks];results=[f.result() for f in futures]
 assert len(results)==8
 index={'format':'c110919-selected-pair-probe-cpu-matrix-v1','manifest_sha256':sha(MANIFEST),'cases':2,'candidates':8,'results':results,'canonical_selected':False,'original_native_accepted':False}
 out=HERE/'update017-selected-pair-probe-index.json';out.write_text(json.dumps(index,indent=2)+'\n')
 print(json.dumps({'cases':2,'candidates':8,'index_sha256':sha(out)}))
if __name__=='__main__':main()
