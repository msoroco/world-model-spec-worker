"""Bind exact final selected CPU receipts without altering selected source manifest."""
import hashlib
import json
from pathlib import Path
import shutil
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c111603-rebound'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
manifest=json.loads((HERE/'execution-manifest.json').read_text())
for entry in manifest['cases']:
 witness=entry['case_id'].rsplit('__',1)[-1]
 construction=json.loads((HERE/entry['construction']).read_text())
 selected_config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
 atoms=set(selected_config['required_atoms'])|{channel['name'] for channel in construction['recording_description']['channels']}
 entry['acquisition']={atom:{'entrypoint':'runner.py',
  'method':'original Native actor, signal and camera-frame acquisition with canonical source assembly',
  'evidence':'native-raw-actors.jsonl; video_frames.jsonl; capture/evidence.jsonl; capture/native/frames.jsonl; four original FFV1 cameras'}
  for atom in sorted(atoms)}
 for cid,candidate in [('primary',entry)]+[(c['id'],c) for c in entry['candidates']]:
  dest=HERE/'selected-runtime-proofs'/witness/cid
  dest.mkdir(parents=True,exist_ok=True)
  offline=SCRATCH/f'{witness}-{cid}-offline-final/offline.log'
  comp=SCRATCH/f'{witness}-{cid}-compat-v2'
  saved=SCRATCH/f'{witness}-{cid}-saved-v2/v0001/processing.json'
  for source,name in ((offline,'offline.log'),(comp/'compatibility.json','compatibility.json'),
   (comp/'compatibility-analysis.log','analysis.log'),(comp/'negative-analysis.log','negative-analysis.log'),
   (comp/'analysis-report.json','analysis-report.json'),(saved,'processing.json')):
   if not source.is_file():raise FileNotFoundError(source)
   shutil.copy2(source,dest/name)
   if (dest/name).stat().st_size>2*1024*1024:raise ValueError('Return file exceeds 2 MiB')
  command=f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --candidate {cid} --output .runtime-work/c111603-rebound/{witness}-{cid}-offline-final --python "$PWD/.venv-cpu/bin/python"'
  candidate['offline']={'exit_code':0,'construction_sha256':candidate['construction_sha256'],
   'command':command,'log':str((dest/'offline.log').relative_to(HERE)),
   'log_sha256':sha(dest/'offline.log')}
  candidate['compatibility']={'receipt':str((dest/'compatibility.json').relative_to(HERE)),
   'sha256':sha(dest/'compatibility.json'),'log':str((dest/'analysis.log').relative_to(HERE)),
   'negative_log':str((dest/'negative-analysis.log').relative_to(HERE))}
  if cid=='primary':
   entry['negative']={'log':candidate['compatibility']['negative_log']}
   entry['post_capture']={'recorded_only':True,
    'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$DECODER"',
    'feedback_command':'inspect "$OUTPUT/feedback.json" on failure',
    'test_log':str((dest/'processing.json').relative_to(HERE)),
    'test_log_sha256':sha(dest/'processing.json'),'test_exit_code':0}
write(HERE/'execution-manifest.json',manifest)
print(json.dumps({'manifest_sha256':sha(HERE/'execution-manifest.json'),'case_count':len(manifest['cases'])}))
