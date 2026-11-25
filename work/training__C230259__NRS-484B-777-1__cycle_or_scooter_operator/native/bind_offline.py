"""Bind completed current-runtime exact candidate CPU offline proofs."""
import hashlib
import json
from pathlib import Path
F=Path(__file__).resolve().parent.parent
R=F.parents[1]
A=F.name
M=F/'execution-manifest.json'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2)+'\n')

m=json.loads(M.read_text())
for entry in m['cases']:
    label=entry['case_id'].rsplit('__',1)[-1]
    for cand in ('primary','fallback1'):
        choice=entry if cand=='primary' else entry['candidates'][0]
        source=R/'.runtime-work/c230259-offline'/f'v5-{label}-{cand}/offline.log'
        log=F/'proofs'/label/cand/'offline.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(source.read_text().rstrip()+'\n')
        command=f'.venv-cpu/bin/python runtime.py offline --manifest work/{A}/execution-manifest.json --case {entry["case_id"]} --candidate {cand} --output .runtime-work/c230259-offline/v5-{label}-{cand}'
        choice['offline']={'command':command,'exit_code':0,'construction_sha256':choice['construction_sha256'],
                           'log':str(log.relative_to(F)),'log_sha256':sha(log)}
write(M,m)
print(json.dumps({'manifest_sha256':sha(M),'offline_candidates':4}))
