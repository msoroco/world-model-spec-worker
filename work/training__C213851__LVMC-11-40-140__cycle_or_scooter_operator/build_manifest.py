"""Bind exact C213851 CPU proofs to current-runtime delivery manifest."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def offline(case,suffix,candidate,construction_hash):
    log=HERE/f'proof-offline-{suffix}-{candidate}.log'
    return {'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-offline-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c213851-offline-v5-{suffix}-{candidate}',
        'construction_sha256':construction_hash,'exit_code':0,
        'log':log.name,'log_sha256':sha(log)}


def compatibility(suffix,candidate):
    folder=HERE/'cases'/suffix
    receipt=folder/f'{candidate}-compatibility.json'
    return {'receipt':str(receipt.relative_to(HERE)),'sha256':sha(receipt),
        'log':str((folder/f'{candidate}-compatibility-analysis.log').relative_to(HERE)),
        'negative_log':str((folder/f'{candidate}-negative-analysis.log').relative_to(HERE))}


def delivery(case,suffix):
    script=HERE/'native/delivery_audit.py'
    positive=HERE/f'delivery-{suffix}-selftest.log'
    negative=HERE/f'delivery-{suffix}-negative-selftest.log'
    base=f'.venv-cpu/bin/python work/{AID}/native/delivery_audit.py --case {case}'
    return {'case_id':case,'sets':['full-train'],
        'checks':['native_source','all_participants','time_join','full_video_decode',
            'actual_pixels','physical_completion'],
        'script':'native/delivery_audit.py','script_sha256':sha(script),
        'command':base+' --selftest','test_exit_code':0,
        'test_log':positive.name,'test_log_sha256':sha(positive),
        'negative_command':base+' --negative-selftest','negative_exit_code':1,
        'negative_expected_error':'Missing delivery source: sidewalk-native.jsonl',
        'negative_log':negative.name,'negative_log_sha256':sha(negative),
        'scope':'Synthetic CPU audit mechanics only; original Native and legal review remain source gated'}


def main():
    manifest=json.loads((HERE/'compat-draft-manifest.json').read_text())
    manifest['status']='delivery_prepared'
    manifest['delivery_ready']=True
    for entry in manifest['cases']:
        case=entry['case_id']
        suffix=case.rsplit('__',1)[-1]
        entry['construction_sha256']=sha(HERE/entry['construction'])
        entry['offline']=offline(case,suffix,'primary',entry['construction_sha256'])
        proof=HERE/'physical-proof'/suffix/'proof.json'
        entry['physical_preparation']={'receipt':str(proof.relative_to(HERE)),
            'sha256':sha(proof)}
        entry['compatibility']=compatibility(suffix,'primary')
        entry['negative']={'log':f'cases/{suffix}/primary-negative-analysis.log'}
        for candidate in entry['candidates']:
            candidate['construction_sha256']=sha(HERE/candidate['construction'])
            candidate['offline']=offline(case,suffix,candidate['id'],candidate['construction_sha256'])
            candidate['compatibility']=compatibility(suffix,candidate['id'])
        entry['acquisition']={name:{'entrypoint':'finalize_sidewalk.py',
            'method':'Native rider/pedestrian pose joined to reviewed district, driveway, sidewalk and conflict sources',
            'evidence':'video_frames.jsonl,sidewalk-native.jsonl,sidewalk_context.json'}
            for name in ('kin.position','kin.speed','ru.bicycle','ru.electric_bicycle','ru.electric_scooter',
                'st.alley','st.driveway_or_alley_entrance','st.sidewalk','drv.stopped',
                'drv.crossing_line','ru.pedestrian','drv.yields_to','drv.time_to_conflict')}
        entry['delivery_acceptance']=delivery(case,suffix)
        receipt=HERE/'cases'/suffix/'process-saved.json'
        saved=HERE/f'saved-{suffix}.log'
        entry['post_capture']={'recorded_only':True,
            'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$ADAPTER_CHECK" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'feedback_command':'cat "$SAVED_VERSION/processing.json"',
            'test_command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/compat-draft-manifest.json --case {case} --attempt .runtime-work/c213851-compat-{suffix}-primary-v5 --output .runtime-work/c213851-saved-v5-{suffix} --library runtime/library --validator "$ADAPTER_CHECK"',
            'test_exit_code':0,'test_log':saved.name,'test_log_sha256':sha(saved),
            'test_receipt':str(receipt.relative_to(HERE)),'test_receipt_sha256':sha(receipt)}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':[e['case_id'] for e in manifest['cases']],
        'manifest_sha256':sha(HERE/'execution-manifest.json')},sort_keys=True))


if __name__=='__main__':
    main()
