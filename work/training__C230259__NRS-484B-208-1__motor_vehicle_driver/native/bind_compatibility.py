"""Bind selected public positive and missing-source negative receipts."""
import hashlib
import json
import shutil
from pathlib import Path
F=Path(__file__).resolve().parent.parent
R=F.parents[1]
M=F/'execution-manifest.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o): p.write_text(json.dumps(o,indent=2)+'\n')
m=json.loads(M.read_text())
for entry in m['cases']:
 label=entry['case_id'].rsplit('__',1)[-1]
 for cand in ('primary','fallback1'):
  choice=entry if cand=='primary' else entry['candidates'][0]
  source=R/'.runtime-work/c230259-208-compat'/f'v4-{label}-{cand}'
  target=F/'proofs'/label/cand
  target.mkdir(parents=True,exist_ok=True)
  for original,dest in [('compatibility.json','compatibility.json'),('compatibility-analysis.log','analysis.log'),('negative-analysis.log','negative-analysis.log')]:
   shutil.copyfile(source/original,target/dest)
  if sha(target/'analysis.log')!=json.loads((target/'compatibility.json').read_text())['log_sha256']:
   raise ValueError('Copied compatibility analysis log differs')
  choice['compatibility']={'receipt':str((target/'compatibility.json').relative_to(F)),
                           'sha256':sha(target/'compatibility.json'),
                           'log':str((target/'analysis.log').relative_to(F)),
                           'negative_log':str((target/'negative-analysis.log').relative_to(F))}
  choice['negative']={'log':str((target/'negative-analysis.log').relative_to(F))}
write(M,m)
print(json.dumps({'manifest_sha256':sha(M),'public_receipts':4}))
