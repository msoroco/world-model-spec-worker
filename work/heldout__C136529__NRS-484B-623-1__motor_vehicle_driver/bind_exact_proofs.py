"""Bind the retained exact offline, compatibility and saved-only CPU proofs."""
import hashlib
import json
from pathlib import Path
from shutil import copyfile
root=Path(__file__).resolve().parent
repo=root.parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    case=entry['case_id'];branch=case.split('__')[-1]
    for candidate,item in [('primary',entry)]+[(x['id'],x) for x in entry['candidates']]:
        stem=branch+'-'+candidate
        offline_dir=repo/'.runtime-work'/('c136529-'+stem+'-offline-v3')
        compat_dir=repo/'.runtime-work'/('c136529-'+stem+'-compat-v3')
        outputs=[('offline.log',offline_dir/'offline.log'),
                 ('compatibility.json',compat_dir/'compatibility.json'),
                 ('compat.log',compat_dir/'compatibility-analysis.log'),
                 ('negative.log',compat_dir/'negative-analysis.log')]
        for suffix,source in outputs:copyfile(source,root/(stem+'-'+suffix))
        item['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{root.name}/execution-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c136529-{stem}-offline-v3 --python "$PWD/.venv-cpu/bin/python"',
                         'exit_code':0,'log':stem+'-offline.log',
                         'log_sha256':sha(root/(stem+'-offline.log')),
                         'construction_sha256':item['construction_sha256']}
        item['compatibility']={'receipt':stem+'-compatibility.json',
                               'sha256':sha(root/(stem+'-compatibility.json')),
                               'log':stem+'-compat.log','negative_log':stem+'-negative.log'}
    entry['negative']={'log':branch+'-primary-negative.log'}
    entry['acquisition']={name:{'entrypoint':'slow_capture_session.py',
       'method':'Original Native participant state at the joined frame; derived after capture by slow_finalizer.py',
       'evidence':'participant_state.jsonl and video_frames.jsonl'}
       for name in ('ego_speed_mps','follower_speed_mps','follower_gap_m')}
    entry['post_capture']={'recorded_only':True,
       'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{root.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
       'feedback_command':'cat "$PROCESSED"/v*/feedback.json',
       'test_log':'saved-processing.log','test_log_sha256':sha(root/'saved-processing.log'),
       'test_exit_code':0}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print('bound',len(manifest['cases']),'exact cases, four constructions each')
