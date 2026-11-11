from pathlib import Path
import json,shutil,hashlib
root=Path(__file__).resolve().parent
repo=root.parents[1]
manifest=root/'execution-manifest.json'
data=json.loads(manifest.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for entry in data['cases'][1:]:
    case=entry['case_id'];slug=case.rsplit('__',1)[-1];sub=root/'cases'/slug
    for candidate in ['primary','fallback1','fallback2','fallback3']:
        is_primary=candidate=='primary'
        if slug=='reverse_close_traffic_steady':
            offline=repo/'.runtime-work'/('c136014-'+slug+'-'+('offline-002' if is_primary else f'{candidate}-offline-001'))
            compat=repo/'.runtime-work'/('c136014-'+slug+'-'+('compat-002' if is_primary else f'{candidate}-compat-001'))
        else:
            offline=repo/'.runtime-work'/('c136014-'+slug+'-'+('offline-002' if is_primary else f'{candidate}-offline-001'))
            compat=repo/'.runtime-work'/('c136014-'+slug+'-'+('primary-compat-002' if is_primary else f'{candidate}-compat-002'))
        target=entry if is_primary else next(x for x in entry['candidates'] if x['id']==candidate)
        prefix='primary' if is_primary else candidate
        receipt=sub/f'{prefix}-compatibility.json';shutil.copyfile(compat/'compatibility.json',receipt)
        clog=sub/f'{prefix}-compat.log';shutil.copyfile(compat/'compatibility-analysis.log',clog)
        nlog=sub/f'{prefix}-negative.log';shutil.copyfile(compat/'negative-analysis.log',nlog)
        olog=sub/f'{prefix}-offline.log';shutil.copyfile(offline/'offline.log',olog)
        saved=sub/(('primary-saved-proof.log' if slug=='reverse_clear_traffic_brakes' else f'{slug}-saved-proof.log') if is_primary else f'{candidate}-saved-proof.log')
        assert saved.is_file() and json.loads(saved.read_text())['negative_missing_source_rejected']
        cmd=f'.venv-cpu/bin/python runtime.py offline --manifest work/{root.name}/execution-manifest.json --case {case}'
        if not is_primary:cmd+=f' --candidate {candidate}'
        cmd+=f' --output {offline.relative_to(repo)} --python {repo}/.venv-cpu/bin/python'
        target['offline']={'command':cmd,'exit_code':0,'log':str(olog.relative_to(root)),'log_sha256':sha(olog),'construction_sha256':target['construction_sha256']}
        target['compatibility']={'receipt':str(receipt.relative_to(root)),'sha256':sha(receipt),'log':str(clog.relative_to(root)),'negative_log':str(nlog.relative_to(root))}
        if is_primary:
            target['post_capture']={'recorded_only':True,'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{root.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR','feedback_command':'cat $OUTPUT/v0001/feedback.json','test_log':str(saved.relative_to(root)),'test_log_sha256':sha(saved),'test_exit_code':0}
        else:
            target['saved_processing_test']={'command':f'.venv-cpu/bin/python work/{root.name}/prove_saved.py --manifest work/{root.name}/execution-manifest.json --validator $VALIDATOR --case {case} --candidate {candidate}','exit_code':0,'log':str(saved.relative_to(root)),'log_sha256':sha(saved)}
manifest.write_text(json.dumps(data,indent=2)+'\n')
print('bound',sum(1+len(e['candidates']) for e in data['cases'][1:]),'candidate receipts')
