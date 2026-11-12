"""Bind passing primary software proofs while retaining partial status."""
import json
from pathlib import Path
from hashlib import sha256
from shutil import copyfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__passing_left'
def sha(path):return sha256(Path(path).read_bytes()).hexdigest()
def bind():
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry=next(item for item in manifest['cases'] if item['case_id']==CASE)
    source=ROOT/'.runtime-work/c230259-passing-left-compat-3'
    copies={
      'passing-left-compatibility.json':source/'compatibility.json',
      'passing-left-compat-analysis.log':source/'compatibility-analysis.log',
      'passing-left-negative.log':source/'negative-analysis.log',
      'passing-left-offline-tests.log':ROOT/'.runtime-work/c230259-passing-left-offline-3/offline.log',
      'passing-left-saved-processing.json':ROOT/'.runtime-work/c230259-passing-left-saved-3/v0001/processing.json',
      'passing-left-saved-analysis.log':ROOT/'.runtime-work/c230259-passing-left-saved-3/v0001/analysis.log'}
    for name,path in copies.items():copyfile(path,HERE/name)
    receipt=json.loads((HERE/'passing-left-compatibility.json').read_text())
    if receipt['construction_sha256']!=entry['construction_sha256']:raise ValueError('Passing proof stale')
    saved=json.loads((HERE/'passing-left-saved-processing.json').read_text())
    if saved['missing_evidence'] or not saved['originals_preserved']:raise ValueError('Passing saved analysis incomplete')
    entry['acquisition']={'right_half_observation':{
       'entrypoint':'passing_runner.py','method':'160-frame Native full-body and directed road recorder with passing setup',
       'evidence':'ego_road_frames.jsonl, road_exception_context.json, trace.jsonl, video_frames.jsonl'}}
    entry['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --output .runtime-work/c230259-passing-left-offline-3',
       'exit_code':0,'log':'passing-left-offline-tests.log','log_sha256':sha(HERE/'passing-left-offline-tests.log'),
       'construction_sha256':entry['construction_sha256']}
    entry['compatibility']={'receipt':'passing-left-compatibility.json',
       'sha256':sha(HERE/'passing-left-compatibility.json'),
       'log':'passing-left-compat-analysis.log','negative_log':'passing-left-negative.log'}
    entry['negative']={'log':'passing-left-negative.log'}
    entry['post_capture']={'recorded_only':True,
       'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
       'feedback_command':'cat "$PROCESSING_OUTPUT/v0001/feedback.json"',
       'test_log':'passing-left-saved.log','test_log_sha256':sha(HERE/'passing-left-saved.log'),
       'test_exit_code':0}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'manifest_sha256':sha(manifest_path),'passing_construction_sha256':entry['construction_sha256']}
if __name__=='__main__':print(json.dumps(bind()))
