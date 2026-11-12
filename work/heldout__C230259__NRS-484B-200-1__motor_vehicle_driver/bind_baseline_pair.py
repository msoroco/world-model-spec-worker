"""Bind current two-case baseline proofs, preserving partial delivery status."""
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p): return sha256(Path(p).read_bytes()).hexdigest()
def bind():
    path=HERE/'execution-manifest.json'; manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        side=entry['case_id'].rsplit('_',1)[-1]
        if side not in ('right','left'): raise ValueError('Only baseline pair supported')
        base=ROOT/f'.runtime-work/c230259-baseline-{side}'
        compat=Path(str(base)+'-compat-4')
        saved=Path(str(base)+'-saved-3/v0001')
        offline=Path(str(base)+'-offline-3/offline.log')
        copies={
            f'baseline-{side}-compatibility.json':compat/'compatibility.json',
            f'baseline-{side}-compat-analysis.log':compat/'compatibility-analysis.log',
            f'baseline-{side}-negative.log':compat/'negative-analysis.log',
            f'baseline-{side}-offline-tests.log':offline,
            f'baseline-{side}-saved-processing.json':saved/'processing.json',
            f'baseline-{side}-saved-analysis.log':saved/'analysis.log'}
        for name,src in copies.items(): copyfile(src,HERE/name)
        receipt=json.loads((HERE/f'baseline-{side}-compatibility.json').read_text())
        if receipt['construction_sha256']!=entry['construction_sha256']: raise ValueError('Stale baseline construction')
        saved_receipt=json.loads((HERE/f'baseline-{side}-saved-processing.json').read_text())
        if saved_receipt['missing_evidence'] or not saved_receipt['originals_preserved']:
            raise ValueError('Incomplete saved baseline')
        entry['acquisition']={'right_half_observation':{
            'entrypoint':'runner.py','method':'20 Hz Native full-body road reference recorder',
            'evidence':'ego_road_frames.jsonl, road_exception_context.json, trace.jsonl, video_frames.jsonl'}}
        entry['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --output .runtime-work/c230259-baseline-{side}-offline-3',
                          'exit_code':0,'log':f'baseline-{side}-offline-tests.log',
                          'log_sha256':sha(HERE/f'baseline-{side}-offline-tests.log'),
                          'construction_sha256':entry['construction_sha256']}
        entry['compatibility']={'receipt':f'baseline-{side}-compatibility.json',
                                'sha256':sha(HERE/f'baseline-{side}-compatibility.json'),
                                'log':f'baseline-{side}-compat-analysis.log',
                                'negative_log':f'baseline-{side}-negative.log'}
        entry['negative']={'log':f'baseline-{side}-negative.log'}
        entry['post_capture']={'recorded_only':True,
            'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
            'feedback_command':'cat "$PROCESSING_OUTPUT/v0001/feedback.json"',
            'test_log':f'baseline-{side}-saved-current.log',
            'test_log_sha256':sha(HERE/f'baseline-{side}-saved-current.log'),
            'test_exit_code':0}
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'manifest_sha256':sha(path),'cases':len(manifest['cases'])}
if __name__=='__main__': print(json.dumps(bind()))
