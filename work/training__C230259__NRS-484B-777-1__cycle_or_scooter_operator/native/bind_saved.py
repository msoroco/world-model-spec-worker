"""Bind recorded-only selected saved processing receipts."""
import hashlib,json,shutil
from pathlib import Path
F=Path(__file__).resolve().parent.parent
R=F.parents[1];M=F/'execution-manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
m=json.loads(M.read_text())
for entry in m['cases']:
 label=entry['case_id'].rsplit('__',1)[-1]
 for cand in ('primary','fallback1'):
  choice=entry if cand=='primary' else entry['candidates'][0]
  source=R/'.runtime-work/c230259-saved'/f'{label}-{cand}-derived/v0001/processing.json'
  proof=F/'proofs'/label/cand/'processing.json'
  shutil.copyfile(source,proof)
  receipt=json.loads(proof.read_text())
  if not receipt['passed'] or receipt['missing_evidence'] or not receipt['recorded_only'] or not receipt['originals_preserved']:
   raise ValueError('Saved processing proof incomplete')
  choice['saved_processing']={'receipt':str(proof.relative_to(F)),'sha256':sha(proof)}
 entry['post_capture']={'recorded_only':True,
   'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{F.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$VALIDATOR"',
   'feedback_command':'cat "$PROCESSED_OUT/v0001/feedback.json"',
   'test_exit_code':0,'proof':entry['saved_processing']['receipt']}
write(M,m)
print(json.dumps({'manifest_sha256':sha(M),'saved_receipts':4}))
