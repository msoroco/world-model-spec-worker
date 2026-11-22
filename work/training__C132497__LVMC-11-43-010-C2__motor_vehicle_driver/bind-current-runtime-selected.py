"""Bind the exact current-runtime C132497 CPU receipts to the canonical handoff."""
import hashlib, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def require(ok,msg):
    if not ok: raise ValueError(msg)
def main():
    runtime_sha=sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    harness=HERE/'current-runtime-reproof-manifest.json'
    source=read(harness)
    matrix=read(HERE/'current-runtime-matrix-progress.json')
    offline=read(HERE/'current-runtime-offline-reproof.json')
    audit=read(HERE/'current-runtime-selected-source-audit.json')
    comparison=read(HERE/'current-runtime-pair-audit.json')
    require(source['runtime_manifest_sha256']==runtime_sha and matrix['completed']==8 and
            len(offline['rows'])==8 and len(audit['rows'])==8 and
            comparison['passed'] is True and comparison['pair_count']==4 and
            len(comparison['negative_rejections'])==2,'Current selected proof set incomplete')
    canonical=HERE/'execution-manifest.json'
    history=HERE/'historical-execution-manifest-pre-cutover.json'
    if not history.exists(): shutil.copyfile(canonical,history)
    manifest=read(history)
    require(manifest['runtime_manifest_sha256']!=runtime_sha,'Expected a historical manifest')
    for entry in manifest['cases']:
        case=entry['case_id']; suffix=case.removeprefix(HERE.name+'__')
        current=next(e for e in source['cases'] if e['case_id']==case)
        require(entry['construction_sha256']==current['construction_sha256'],'Primary construction changed')
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            selected=entry if candidate=='primary' else next(e for e in entry['candidates'] if e['id']==candidate)
            expected=current if candidate=='primary' else next(e for e in current['candidates'] if e['id']==candidate)
            require(selected['construction_sha256']==expected['construction_sha256'],'Selected construction changed')
            folder=HERE/'current-runtime-selected-proof'/suffix/candidate
            compat=read(folder/'compatibility.json');saved=read(folder/'saved-processing.json')
            off=HERE/'current-runtime-offline'/suffix/(candidate+'.log')
            require(compat['passed'] and compat['runtime_manifest_sha256']==runtime_sha and
                    compat['construction_sha256']==selected['construction_sha256'] and
                    compat['log_sha256']==sha(folder/'analysis.log') and
                    compat['negative_log_sha256']==sha(folder/'negative-analysis.log') and
                    saved['passed'] and saved['recorded_only'] and saved['originals_preserved'] and
                    saved['timestamp_joins']['passed'] and
                    saved['native_revision']['construction_sha256']==selected['construction_sha256'] and
                    read(off)['offline_passed'] and
                    read(folder/'source-camera-audit.json')['saved_processing_sha256']==sha(folder/'saved-processing.json'),
                    'Current exact proof differs: '+suffix+'/'+candidate)
            rel=str(folder.relative_to(HERE))
            selected['offline']={'exit_code':0,'construction_sha256':selected['construction_sha256'],
                'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-runtime-reproof-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c132497-current-offline/{suffix}/{candidate}',
                'log':str(off.relative_to(HERE)),'log_sha256':sha(off)}
            selected['compatibility']={'receipt':rel+'/compatibility.json','sha256':sha(folder/'compatibility.json'),
                'log':rel+'/analysis.log','negative_log':rel+'/negative-analysis.log'}
            selected['saved_processing']={'receipt':rel+'/saved-processing.json','sha256':sha(folder/'saved-processing.json')}
        entry['negative']={'log':f'current-runtime-selected-proof/{suffix}/primary/negative-analysis.log'}
        physical=HERE/'current-runtime-selected-physical'/suffix/'proof.json'
        require(physical.is_file(),'Physical proof missing')
        entry['physical_preparation']={'receipt':str(physical.relative_to(HERE)),'sha256':sha(physical)}
        pos=HERE/f'current-runtime-delivery-{suffix}-positive.log';neg=HERE/f'current-runtime-delivery-{suffix}-negative.log'
        require('cpu_audit_mechanics_passed' in pos.read_text() and
                'Original actor/frame/trace join differs at 0' in neg.read_text(),
                'Delivery positive/negative mechanics differ')
        script=HERE/'prove-delivery-contract.py'
        entry['delivery_acceptance']={'case_id':case,'sets':['full-train'],
            'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
            'script':script.name,'script_sha256':sha(script),
            'command':f'.venv-cpu/bin/python work/{HERE.name}/prove-delivery-contract.py --case {case}',
            'test_exit_code':0,'test_log':pos.name,'test_log_sha256':sha(pos),
            'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/prove-delivery-contract.py --case {case} --reject-synthetic',
            'negative_exit_code':1,'negative_expected_error':'Original actor/frame/trace join differs at 0',
            'negative_log':neg.name,'negative_log_sha256':sha(neg),
            'scope':'Diagnostic CPU mechanics; original Native and pixel acceptance unverified'}
        entry['preparation_status']='selected_cpu_proofs_current_physical_unverified'
    manifest['runtime_manifest_sha256']=runtime_sha
    manifest['status']='selected_cpu_proofs_current_physical_unverified'
    manifest['comparison_audit']={'script':'prove-current-runtime-pairs.py',
        'script_sha256':sha(HERE/'prove-current-runtime-pairs.py'),
        'receipt':'current-runtime-pair-audit.json','receipt_sha256':sha(HERE/'current-runtime-pair-audit.json'),
        'original_native_accepted':False}
    canonical.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'cases':2,'chains':8,'manifest_sha256':sha(canonical)}))
if __name__=='__main__':main()
