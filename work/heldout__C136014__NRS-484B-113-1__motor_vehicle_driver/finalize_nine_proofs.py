"""Bind finished CPU receipts for the nine exact backing cases."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path

r=Path(__file__).resolve().parent
repo=r.parents[1]
mp=r/'execution-manifest.json'
m=json.loads(mp.read_text())
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for e in m['cases']:
    case=e['case_id'];slug=case.rsplit('__',1)[-1]
    sub=r/'cases'/slug if e is not m['cases'][0] else r
    if e is m['cases'][0]:
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            target=e if candidate=='primary' else next(x for x in e['candidates'] if x['id']==candidate)
            offline=repo/'.runtime-work'/f'c136014-primary9-{candidate}-offline'
            compat=repo/'.runtime-work'/f'c136014-primary9-{candidate}-compat'
            log=r/f'{candidate}-nine-offline.log'
            assert offline.is_dir() and compat.is_dir() and log.is_file()
            target['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{r.name}/execution-manifest.json --case {case}'+(f' --candidate {candidate}' if candidate!='primary' else '')+f' --output {offline.relative_to(repo)} --python {repo}/.venv-cpu/bin/python','exit_code':0,'log':str(log.relative_to(r)),'log_sha256':sha(log),'construction_sha256':target['construction_sha256']}
            receipt=r/f'{candidate}-nine-compatibility.json';clog=r/f'{candidate}-nine-compat.log';nlog=r/f'{candidate}-nine-negative.log'
            shutil.copyfile(compat/'compatibility.json',receipt)
            shutil.copyfile(compat/'compatibility-analysis.log',clog)
            shutil.copyfile(compat/'negative-analysis.log',nlog)
            target['compatibility']={'receipt':str(receipt.relative_to(r)),'sha256':sha(receipt),'log':str(clog.relative_to(r)),'negative_log':str(nlog.relative_to(r))}
        e['negative']={'log':'primary-nine-negative.log'}
    if e in m['cases'][3:]:
        e['acquisition']=dict(m['cases'][0]['acquisition'])
        e['negative']={'log':str((sub/'primary-negative.log').relative_to(r))}
    if e is m['cases'][0] or e in m['cases'][3:]:
        attempt=(repo/'.runtime-work'/f'c136014-primary9-primary-compat') if e is m['cases'][0] else (repo/'.runtime-work'/f'c136014-{slug}-primary-compat-006')
        assert attempt.is_dir(),attempt
        pos=sub/('first-nine-delivery-proof.log' if e is m['cases'][0] else 'delivery-proof.log')
        neg=sub/('first-nine-delivery-negative.log' if e is m['cases'][0] else 'delivery-negative.log')
        base=[sys.executable,str(r/'prove_delivery_audit.py'),'--case',case,'--attempt',str(attempt)]
        p=subprocess.run(base,cwd=repo,capture_output=True,text=True);pos.write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(f'delivery positive {slug}: {p.stderr[-600:]}')
        n=subprocess.run(base+['--negative'],cwd=repo,capture_output=True,text=True);neg.write_text(n.stdout+n.stderr)
        assert n.returncode!=0 and 'Missing required source: backing_history.jsonl' in neg.read_text(),slug
        e['delivery_acceptance']={'case_id':case,'sets':['held-out'],'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],'script':'prove_delivery_audit.py','script_sha256':sha(r/'prove_delivery_audit.py'),'command':f'.venv-cpu/bin/python work/{r.name}/prove_delivery_audit.py --case {case} --attempt {attempt.relative_to(repo)}','test_exit_code':0,'test_log':str(pos.relative_to(r)),'test_log_sha256':sha(pos),'negative_command':f'.venv-cpu/bin/python work/{r.name}/prove_delivery_audit.py --case {case} --attempt {attempt.relative_to(repo)} --negative','negative_exit_code':n.returncode,'negative_expected_error':'Missing required source: backing_history.jsonl','negative_log':str(neg.relative_to(r)),'negative_log_sha256':sha(neg),'scope':'CPU fixture source audit; physical and legal acceptance remain pending'}
    if e is m['cases'][0] or e in m['cases'][3:]:
        life=r/'physical'/f'{slug}-lifecycle.log'
        cmd=f'.venv-cpu/bin/python work/{r.name}/lifecycle_fixture.py --case {case}'
        p=subprocess.run([sys.executable,str(r/'lifecycle_fixture.py'),'--case',case],cwd=repo,capture_output=True,text=True)
        life.write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(f'lifecycle {slug}: {p.stderr[-600:]}')
        events=json.loads(p.stdout)['events']
        proof={'construction_sha256':e['construction_sha256'],'fixture_scope':'Synthetic Native-shaped outcome and mocked lifecycle; no actual physical capture or visual body finding','fixtures':[],'lifecycle':{'events':events,'exit_code':0,'log':str(life.relative_to(r)),'log_sha256':sha(life),'test_scope':'Mock runner capture/restoration and bound saved-only proof; actual owner release remains to verify'}}
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            result=r/'physical'/f'{slug}-{kind}.json';log=r/'physical'/f'{slug}-{kind}.log'
            assert result.is_file() and log.is_file(),(result,log)
            proof['fixtures'].append({'kind':kind,'command':f'.venv-cpu/bin/python work/{r.name}/physical_fixture.py --case {case} --kind {kind} --output work/{r.name}/physical/{slug}-{kind}.json','exit_code':0,'log':str(log.relative_to(r)),'log_sha256':sha(log),'result':str(result.relative_to(r)),'result_sha256':sha(result)})
        receipt=r/'physical'/f'{slug}-proof.json';receipt.write_text(json.dumps(proof,indent=2)+'\n')
        e['physical_preparation']={'receipt':str(receipt.relative_to(r)),'sha256':sha(receipt)}
    print(slug,'bound',flush=True)
mp.write_text(json.dumps(m,indent=2)+'\n')
