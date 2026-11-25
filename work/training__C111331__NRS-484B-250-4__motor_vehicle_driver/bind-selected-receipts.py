"""Bind exact CPU receipts while retaining partial delivery status."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE=ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


path=ROOT/'selected-construction-manifest.json'
manifest=json.loads(path.read_text())
for n,entry in enumerate(manifest['cases'],1):
    for name,target in [('primary',entry),('fallback1',entry['candidates'][0])]:
        local=ROOT/'selected-candidates'/f'controlled_{n}'/name
        rel=local.relative_to(ROOT).as_posix()
        offline=local/'offline.log'
        receipt=local/'compatibility.json'
        analysis=local/'analysis.log'
        negative=local/'negative-analysis.log'
        if not all(p.is_file() for p in (offline,receipt,analysis,negative)):
            raise ValueError('Missing exact candidate CPU receipt: '+rel)
        data=json.loads(receipt.read_text())
        if not data.get('passed') or data.get('construction_sha256')!=target['construction_sha256']:
            raise ValueError('Stale candidate compatibility receipt: '+rel)
        target['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/selected-construction-manifest.json --case {entry["case_id"]} --candidate {name} --output .runtime-work/c111331-2504-selected-offline-{n}-{name} --python "$PWD/.venv-cpu/bin/python"',
                           'construction_sha256':target['construction_sha256'],
                           'exit_code':0,'log':rel+'/offline.log','log_sha256':sha(offline)}
        target['compatibility']={'receipt':rel+'/compatibility.json','sha256':sha(receipt),
                                 'log':rel+'/analysis.log',
                                 'log_sha256':sha(analysis),
                                 'negative_log':rel+'/negative-analysis.log',
                                 'negative_log_sha256':sha(negative)}
        if name=='primary':target['negative']={'log':rel+'/negative-analysis.log'}
        processed=local/'processing.json'
        if processed.is_file():
            data=json.loads(processed.read_text())
            if not (data.get('passed') and data.get('recorded_only') and
                    data.get('missing_evidence') is False and
                    data.get('candidate_id') == name):
                raise ValueError('Stale saved processing receipt: '+rel)
            command=(f'.venv-cpu/bin/python runtime.py process-saved --manifest '
                     f'work/{BASE}/selected-construction-manifest.json --case '
                     f'{entry["case_id"]} --attempt $ATTEMPT --output $OUTPUT '
                     f'--library runtime/library --validator $DECODER')
            target['saved_processing']={'receipt':rel+'/processing.json',
                'sha256':sha(processed),'command':command,'test_exit_code':0,
                'recorded_only':True,'missing_evidence':False}
            if name=='primary':
                entry['post_capture']={'command':command,
                    'feedback_command':'cat $OUTPUT/versions/*/feedback.json',
                    'recorded_only':True,'test_exit_code':0,
                    'test_log':rel+'/processing.json',
                    'test_log_sha256':sha(processed)}
manifest['status']='selected_cpu_saved_processing_passed_delivery_partial'
path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
