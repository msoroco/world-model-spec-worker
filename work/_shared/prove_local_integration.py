"""CPU-only canonical handoff integration; no database or simulator is opened."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(ROOT/'.runtime-work/saved-lifecycle-output'))
sys.path[:0] = [str(ROOT/'runtime/scenario_pipeline'), str(ROOT/'runtime/tests'), str(ROOT/'work/_shared')]
from worker_exchange.candidate_constructions import select
from worker_exchange.delivery_handoff import validate_queue
from worker_exchange.local_delivery import _selection_targets
from worker_exchange.common import write, sha
from test_worker_delivery_handoff import DeliveryHandoffTests
from source_audit_contract import check as check_audit
from compare_saved import check as check_comparison

def prove_saved(assignment, case):
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.native_output import seal_capture
    from worker_exchange.runtime_cli import materialize as make_attempt
    from worker_exchange.saved_processing import acknowledge_owner_release, copy_sources, record_native_exit, run
    manifest=ROOT/'work'/assignment/'execution-manifest.json'
    entry=next(x for x in json.loads(manifest.read_text())['cases'] if x['case_id']==case)
    with tempfile.TemporaryDirectory(prefix='cpu-saved-',dir=ROOT/'.runtime-work') as tmp:
        base=Path(tmp);attempt=base/'attempt'
        materialize(ROOT,ROOT/entry['fixture_recipe'],base/'fixture')
        make_attempt(manifest,case,attempt)
        copy_sources(base/'fixture',attempt)
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'fixture_scope':'CPU saved-processing proof only'})+'\n')
        frames=len((attempt/'video_frames.jsonl').read_text().splitlines())
        seal_capture(attempt,frames=frames,restoration={'restored':True},errors=[],
                     encoder_exit_codes={x:0 for x in ('overview','approach','reference_corner','driver_reference')},
                     context={'fixture_scope':'CPU saved-processing proof only'})
        record_native_exit(attempt)
        owner=base/'owner-release.json'
        acknowledge_owner_release(attempt,owner,True)
        validator=ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
        run(manifest,case,attempt,base/'processing',ROOT/'runtime/library',validator,owner_receipt=owner)
        saved=json.loads((base/'processing/v0001/processing.json').read_text())
        if not (saved.get('passed') is True and saved.get('recorded_only') is True and
                saved.get('originals_preserved') is True and saved.get('missing_evidence') is False):
            raise ValueError('Saved-only lifecycle proof did not pass')
        print(case,'saved_processing_passed','synthetic_fixture_only')

def run_wrapped(name):
    test=DeliveryHandoffTests(name)
    test.setUp()
    try:
        getattr(DeliveryHandoffTests,name).__wrapped__(test)
    finally:
        test.doCleanups()

def main():
    batch=json.loads((ROOT/'batch.json').read_text())
    queue=json.loads((ROOT/'work/_shared/gpu-queue.json').read_text())
    if len(queue['cases'])!=361 or len(queue['comparison_audit_commands'])!=237:
        raise ValueError('Exact queue inventory changed')
    row=queue['cases'][0]
    manifest=ROOT/'work'/row['assignment_id']/'execution-manifest.json'
    primary=select(manifest,row['case_id'],'primary')[1]
    fallback=select(manifest,row['case_id'],'fallback1')[1]
    if primary['construction_sha256']==fallback['construction_sha256']:
        raise ValueError('Fallback repeats primary')
    run_wrapped('test_exact_dispatch_cannot_run_other_jobs')
    print('primary_job PASS; exact canonical execution job selected')
    print('fallback_job PASS; current distinct construction hash selected')
    aid=next(a for a in batch['assignments'] if a.startswith('heldout__C178759__'))
    cid=next(c['case_id'] for c in json.loads((ROOT/'work'/aid/'execution-manifest.json').read_text())['cases'] if 'at_mile' in c['case_id'])
    prove_saved(aid,cid)
    print('saved_processing PASS; CPU synthetic fixture, owner release and original preservation')
    sys.modules['review_workspaces']=types.SimpleNamespace(refresh_workspaces=lambda *a,**k:None)
    run_wrapped('test_local_acceptance_references_one_recording_in_both_sets')
    print('rejected_audit PASS; false and stale source audit rejected before selection change')
    print('accepted_both_sets PASS; mocked local acceptance selects same recording in two test sets')
    with tempfile.TemporaryDirectory(prefix='heldout-target-',dir=ROOT/'.runtime-work') as tmp:
        local=Path(tmp)
        assignment={'assignment_id':aid,'role':'heldout','law_id':'LAW','cell_id':'C','actor':'motor_vehicle_driver','selection_targets':['held-out']}
        write(local/'sets/held-out/scope.json',{'assignments':[{'law_id':'LAW','cell_id':'C','actor':'motor_vehicle_driver'}]})
        if _selection_targets(local,assignment)!=['held-out']:
            raise ValueError('Held-out target selection mismatch')
    print('accepted_targets PASS; held-out set selected from frozen-role scope fixture')
    with tempfile.TemporaryDirectory(prefix='audit-contract-',dir=ROOT/'.runtime-work') as tmp:
        local=Path(tmp); attempt=local/'recordings'/'recording'/'evidence';attempt.mkdir(parents=True)
        auditor=local/'state/operations/worker_exchange/held-out-delivery/audit/delivery_audit.py'
        auditor.parent.mkdir(parents=True);auditor.write_text('AUDITOR_VERSION=1\n')
        write(attempt/'result.json',{'completion':{'binding':{}}})
        (attempt/'raw.mkv').write_bytes(b'fixture-only')
        write(attempt/'traffic_spec/trace.json',{'scenes':[{'t':50}]})
        (attempt/'video_frames.jsonl').write_text(json.dumps({'video_frame':0,'time_s':0.05})+'\n')
        from worker_exchange import media
        receipt=auditor.parent/'source-decode.json'
        write(receipt,{'format':'source-decode','passed':True,'auditor_sha256':sha(Path(media.__file__)),
            'video_sha256':sha(attempt/'raw.mkv'),'frames':1,'mapping_sha256':sha(attempt/'video_frames.jsonl'),
            'checks':{'frame_count':'all-decoded-frames'}})
        audit={'format':'worker-delivery-audit','passed':True,'case_id':cid,'checks':{k:True for k in ('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')},
            'source_result_sha256':sha(attempt/'result.json'),'video':'raw.mkv','video_sha256':sha(attempt/'raw.mkv'),
            'trace':'traffic_spec/trace.json','trace_sha256':sha(attempt/'traffic_spec/trace.json'),
            'auditor_path':str(auditor),'auditor_sha256':sha(auditor),'source_decode_receipt_path':str(receipt),
            'source_decode_receipt_sha256':sha(receipt),'source_decode_auditor_sha256':sha(Path(media.__file__)),'frames':1}
        write(attempt/'audit.json',audit)
        if not check_audit(local,'held-out-delivery',cid,attempt,attempt/'audit.json')['passed']:
            raise ValueError('Independent source contract failed')
        audit['checks']['actual_pixels']=False;write(attempt/'audit.json',audit)
        try:check_audit(local,'held-out-delivery',cid,attempt,attempt/'audit.json')
        except ValueError:pass
        else:raise ValueError('Missing pixel review was accepted')
    print('source_audit_contract PASS; original hashes and full-decode receipt; missing pixel check rejected')
    compare=queue['comparison_audit_commands'][0]
    plan=json.loads((ROOT/'work'/compare['assignment_id']/'case-plan.json').read_text())
    definition=next(c for c in plan['comparisons'] if c['comparison_id']==compare['comparison_id'])
    with tempfile.TemporaryDirectory(prefix='comparison-contract-',dir=ROOT/'.runtime-work') as tmp:
        base=Path(tmp)
        report={'format':'worker-native-comparison-review','assignment_id':compare['assignment_id'],
            'comparison_id':compare['comparison_id'],'reviewer':'local CPU contract fixture',
            'diagnostic_fixture':False,'passed':True,'cases':{},'fixed_measurements':{},'difference_measurements':{}}
        for index,case in enumerate(definition['case_ids']):
            attempt=base/str(index);attempt.mkdir()
            (attempt/'raw.mkv').write_bytes(('original-'+str(index)).encode())
            report['cases'][case]={'attempt':str(attempt),'source_sha256':{'raw.mkv':sha(attempt/'raw.mkv')},
                'original_source_paths':['raw.mkv'],'audit_case_id':case,'audit_passed':True}
        for condition in definition['fixed_conditions']:
            report['fixed_measurements'][condition]={case:'same-source-condition' for case in definition['case_ids']}
        for condition in definition['deliberate_differences']:
            report['difference_measurements'][condition]={case:index for index,case in enumerate(definition['case_ids'])}
        path=base/'report.json';write(path,report)
        if not check_comparison(ROOT,compare['assignment_id'],compare['comparison_id'],path)['passed']:
            raise ValueError('Comparison review contract failed')
        (base/'0/raw.mkv').write_bytes(b'tampered')
        try:check_comparison(ROOT,compare['assignment_id'],compare['comparison_id'],path)
        except ValueError:pass
        else:raise ValueError('Changed comparison source was accepted')
    print('comparison_review PASS; all fixed/different fields reviewed; original tamper rejected')
    return ['primary_job','fallback_job','saved_processing','rejected_audit','accepted_both_sets','accepted_targets']

if __name__=='__main__':
    scenarios=main()
    print('scenarios',json.dumps(scenarios))
