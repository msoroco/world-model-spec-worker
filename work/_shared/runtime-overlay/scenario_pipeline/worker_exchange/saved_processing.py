"""Revision-selected saved-only processing into fresh immutable output versions."""
import json,shutil,subprocess,sys
from pathlib import Path
from .common import read,write,sha,within,tree,digest
from .runtime_cli import execution_env,process,render
from .media import audit,compose_four_views

SKIP={'result.json','analysis-report.json','channels','traffic_spec','converted','compatibility.json','processing.json','feedback.json'}

def record_native_exit(attempt):
    attempt=Path(attempt)
    if not (attempt/'capture-seal.json').is_file():
        status=read(attempt/'native-run-status.json')
        if not status.get('errors'):raise ValueError('Unsealed Native exit needs an explicit failed-capture status')
        receipt={'event':'native_exit','capture_failed':True,'capture_seal_sha256':None,'native_revision':{'construction_sha256':sha(attempt/'construction.json'),'runner_sha256':sha(attempt/'runner.py')}}
        write(attempt/'native-exit.json',receipt);return receipt
    seal=read(attempt/'capture-seal.json')
    if seal['events']!=['capture_finished','encoders_closed','restoration_verified']:raise ValueError('Invalid Native closure ordering')
    receipt={'event':'native_exit','capture_seal_sha256':sha(attempt/'capture-seal.json'),'native_revision':seal['native_revision']}
    write(attempt/'native-exit.json',receipt);return receipt

def acknowledge_owner_release(attempt,receipt,acknowledged):
    if not acknowledged:raise ValueError('Operator must attest actual owner release; this command never releases resources')
    attempt=Path(attempt);path=Path(receipt)
    if path.exists():raise ValueError('Retain previous owner-release receipt')
    if (attempt/'capture-seal.json').is_file() and not (attempt/'native-exit.json').is_file():raise ValueError('Native process has not exited')
    value={'event':'owner_released','operator_attested':True,'native_construction_sha256':sha(attempt/'construction.json'),
           'native_exit_sha256':sha(attempt/'native-exit.json') if (attempt/'native-exit.json').is_file() else None,
           'no_resource_operation_performed':True}
    write(path,value);return value

def _closure(attempt,owner_receipt,kind,diagnostic):
    if (attempt/'capture-seal.json').is_file():
        seal=read(attempt/'capture-seal.json')
        for name,checksum in seal['sources'].items():
            if sha(within(attempt,name))!=checksum:raise ValueError('Sealed original changed: '+name)
        exit_record=read(attempt/'native-exit.json')
        if exit_record.get('event')!='native_exit' or exit_record.get('native_revision')!=seal['native_revision'] or exit_record['capture_seal_sha256']!=sha(attempt/'capture-seal.json'):raise ValueError('Native exit receipt differs')
    if owner_receipt:
        owner=read(owner_receipt)
        if owner.get('event')!='owner_released' or owner.get('operator_attested') is not True or owner['native_construction_sha256']!=sha(attempt/'construction.json'):raise ValueError('Owner release not attested for this capture')
        if (attempt/'native-exit.json').is_file() and owner.get('native_exit_sha256')!=sha(attempt/'native-exit.json'):raise ValueError('Owner release references a different Native exit')
    elif kind=='native' and not diagnostic:raise ValueError('Supply an operator owner-release receipt before saved processing')

def _workspace(attempt,version,construction,analysis_entry):
    stage=version/'analysis';stage.mkdir()
    for p in attempt.iterdir():
        if p.name in SKIP or p.name.startswith(('source-','final-decode','primary','annotated')):continue
        q=stage/p.name
        if p.is_dir():shutil.copytree(p,q)
        else:shutil.copy2(p,q)
    # Keep original Native config/scene/runner. Select the current analyzer and helpers explicitly.
    for item in construction['files']:
        if item['path'].endswith('.py') and item['path']!='runner.py' and not item['path'].startswith('tests/'):
            q=within(stage,item['path']);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(item['content'])
    return stage

def run(manifest,case,attempt,output,library,validator,owner_receipt=None):
    from .native_output import provenance_record,missing_evidence_result
    manifest,attempt,output=Path(manifest).resolve(),Path(attempt).resolve(),Path(output).resolve()
    if attempt==output or attempt in output.parents:raise ValueError('Derived output must be outside original acquisition')
    output.mkdir(parents=True,exist_ok=True)
    index=1
    while (output/('v%04d'%index)).exists():index+=1
    version=output/('v%04d'%index);version.mkdir()
    before=tree(attempt)
    try:
        entry=next(e for e in read(manifest)['cases'] if e['case_id']==case)
        construction=read(within(manifest.parent,entry['construction']))
        if sha(within(manifest.parent,entry['construction']))!=entry['construction_sha256']:raise ValueError('Selected construction changed')
        original=read(attempt/'construction.json');config=read(attempt/'config.json')
        if original['case_id']!=case or config.get('selected_case_id',config.get('case',{}).get('case_id'))!=case:raise ValueError('Wrong Native case identity')
        provenance=provenance_record(attempt)
        legacy_binding=None
        if entry.get('native_construction_sha256'):
            capture_manifest=read(attempt/'capture/manifest.json')
            if config.get('case',{}).get('case_id')!=case or capture_manifest.get('case_id')!=case:
                raise ValueError('Legacy embedded case identity differs')
            expected_native=entry['native_construction_sha256'];actual_native=sha(attempt/'construction.json')
            diagnostic_marker=read(attempt/'acquisition-provenance.json') if (attempt/'acquisition-provenance.json').is_file() else {}
            diagnostic_exception=(diagnostic_marker.get('diagnostic_fixture') is True and diagnostic_marker.get('provenance_kind')=='native')
            if actual_native!=expected_native and not diagnostic_exception:
                raise ValueError('Legacy Native construction hash differs from frozen retained capture')
            legacy_binding={'expected_native_construction_sha256':expected_native,'actual_native_construction_sha256':actual_native,'original_hash_matched':actual_native==expected_native,'explicit_diagnostic_exception':actual_native!=expected_native and diagnostic_exception,'actual_recording_audited':False}
        _closure(attempt,owner_receipt,provenance['provenance_kind'],provenance['diagnostic_fixture'])
        stage=_workspace(attempt,version,construction,entry['measurement_procedure']['entrypoint'])
        if not (stage/'raw.mkv').exists():
            composition=compose_four_views({n:stage/(n+'.mkv') for n in ('overview','approach','reference_corner','driver_reference')},stage/'video_frames.jsonl',stage/'raw.mkv')
            write(stage/'four-view-receipt.json',composition)
        analysis=within(stage,entry['measurement_procedure']['entrypoint'])
        staged_sources=tree(stage)
        with (version/'analysis.log').open('x') as log:
            completed=subprocess.run([sys.executable,str(analysis),'--attempt',str(stage),'--output',str(stage/'analysis-report.json')],cwd=stage,env=execution_env(),stdout=log,stderr=subprocess.STDOUT,timeout=600)
        if any(sha(stage/name)!=checksum for name,checksum in staged_sources.items()):raise ValueError('Selected analyzer rewrote staged original source')
        missing=False
        if completed.returncode:
            error=(version/'analysis.log').read_text()
            if not any(label in error for label in ('Missing required source:','FileNotFoundError','ValueError:','KeyError:')):raise ValueError('Selected analyzer failed: '+error[-2000:])
            missing=True;result=missing_evidence_result(stage,error[-2000:])
            from .native_output import physical_result
            if config.get('law_id'):
                result=physical_result(stage,result)
                write(stage/'result.json',result)
            result['analysis_complete']=False
            write(stage/'result.json',result)
            write(stage/'analysis-report.json',{'format':'worker-analysis-report-v1','case_id':case,'measurements':{},'physical_checks':result['physical_checks'],'realized_observables':result['realized_observables'],'provenance_kind':result['provenance_kind'],'diagnostic_fixture':result['diagnostic_fixture'],'limitations':['Selected law analysis could not complete: '+error[-2000:]],'analysis_complete':False})
            write(version/'feedback.json',{'recorded_only':True,'native_replay_requested':False,'classification':'incomplete_or_unavailable_law_evidence','physical_status':result['physical_checks']['maneuver']['status'],'error':error[-2000:]})
        else:result=read(stage/'result.json')
        from .native_output import validate_result
        validate_result(result)
        rows=[json.loads(s) for s in (stage/'trace.jsonl').read_text().splitlines() if s] if (stage/'trace.jsonl').is_file() else []
        mapping=[json.loads(s) for s in (stage/'video_frames.jsonl').read_text().splitlines() if s] if (stage/'video_frames.jsonl').is_file() else []
        if (not missing or (rows and mapping)) and (len(rows)!=len(mapping) or any(r['frame']!=m['carla_frame'] or abs(r['time_s']-m['time_s'])>1e-6 for r,m in zip(rows,mapping))):raise ValueError('Original timestamp/frame joins differ')
        final_video=None
        if not missing:
            from batch_pipeline.carla import validate_attempt
            audits={v:audit(within(stage,v),len(rows),mapping_sha256=sha(stage/'video_frames.jsonl'),receipt=version/('source-'+str(i)+'.json')) for i,v in enumerate(result['video_references'])}
            proposal=next(c for c in read(manifest.parent/'proposals/cases.json')['cases'] if c['case_id']==case)
            validate_attempt(stage,{'case':proposal,'cell':{'cell_id':config['cell_id']},'actor':config['actor']},construction,{'recorded_exit_code':0},{},source_audits=audits)
            write(stage/'result.json',result)
            process(stage,version/'converted',library,validator)
            video=render(stage,version/'converted',proposal)
            final_video=audit(video['video'],len(rows),receipt=version/'final-decode.json')
        if missing and rows and mapping:
            try:
                audit(stage/'raw.mkv',len(rows),mapping_sha256=sha(stage/'video_frames.jsonl'),receipt=version/'partial-source-decode.json')
                process(stage,version/'converted',library,validator)
                proposal=next(c for c in read(manifest.parent/'proposals/cases.json')['cases'] if c['case_id']==case)
                video=render(stage,version/'converted',proposal)
                final_video=audit(video['video'],len(rows),receipt=version/'partial-final-decode.json')
            except Exception as partial_error:
                write(version/'partial-media-feedback.json',{'recorded_only':True,'error':str(partial_error),'law_analysis_complete':False,'native_replay_requested':False})
        if tree(attempt)!=before:raise ValueError('Saved processing rewrote original acquisition or prior results')
        receipt={'format':'worker-saved-processing-v2','case_id':case,'passed':True,'recorded_only':True,
          'version':str(version),'analysis_directory':str(stage),'result':str(stage/'result.json'),
          'native_revision':{'construction_sha256':sha(attempt/'construction.json'),'analyzer_sha256':sha(attempt/entry['measurement_procedure']['entrypoint']) if (attempt/entry['measurement_procedure']['entrypoint']).is_file() else None},
          'analysis_revision':{'construction_sha256':entry['construction_sha256'],'analyzer_sha256':sha(analysis),'runtime_manifest_sha256':read(manifest)['runtime_manifest_sha256']},
          'original_source_hashes':before,'originals_preserved':True,'timestamp_joins':{'frames':len(rows),'passed':bool(rows and mapping),'missing_original_trace_or_map':not bool(rows and mapping)},
          'analysis_log_sha256':sha(version/'analysis.log'),'result_sha256':sha(stage/'result.json'),'final_video_checks':final_video,
          'missing_evidence':missing,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
          'events':['saved_processing_started','selected_analysis_executed','originals_verified'],
          'remaining':['original pixels and actual physical completion review','unresolved legal judgments']}
        if legacy_binding is not None:receipt['legacy_native_binding']=legacy_binding
        write(version/'processing.json',receipt);return receipt
    except Exception as error:
        write(version/'feedback.json',{'case_id':case,'recorded_only':True,'error_type':type(error).__name__,'error':str(error),'manifest_sha256':sha(manifest),'native_replay_requested':False})
        if tree(attempt)!=before:raise ValueError('Original source preservation failed') from error
        raise
