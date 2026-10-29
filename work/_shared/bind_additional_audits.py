"""Bind passing saved source-join diagnostics and future Native audit commands."""
import hashlib,json,shlex,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 proof=read(ROOT/'work/_shared/source-join-proof.json')
 if not proof['passed']:raise ValueError('Exact source joins must all pass before binding')
 cases={c['case_id']:c for c in proof['cases']}
 for path in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  folder=path.parent;m=read(path);receipts=folder/'receipts'
  selected=[cases[c['case_id']] for c in m['cases']]
  receipt=receipts/'source-frame-joins.json';write(receipt,{'passed':True,'cases':selected,'physical_acceptance_claimed':False})
  log=receipts/'source-frame-joins.log';shutil.copyfile(ROOT/'work/_shared/source-join-tests002.log',log)
  for c in m['cases']:
   tokens=shlex.split(c['post_capture']['command']);attempt=tokens[tokens.index('--output')+1]+'/v0001/analysis'
   c['post_capture']['additional_source_audit_command']='python3.11 work/_shared/source_audit.py --spec work/_shared/source-audit-specs.json --case '+c['case_id']+' --attempt '+attempt+' --output '+attempt+'/additional-source-audit.json'
   c['post_capture']['source_join_fixture_proof']={'receipt':'receipts/source-frame-joins.json','receipt_sha256':sha(receipt),'test_log':'receipts/source-frame-joins.log','test_log_sha256':sha(log),'test_exit_code':0}
  write(path,m)
  result=read(folder/'result.json');result['tests'].append({'command':'python3.11 work/_shared/prove_source_joins.py','exit_code':0,'log':'receipts/source-frame-joins.log','sha256':sha(log)});write(folder/'result.json',result)
 print('Bound additional saved source audits to all exact manifests')
if __name__=='__main__':main()
