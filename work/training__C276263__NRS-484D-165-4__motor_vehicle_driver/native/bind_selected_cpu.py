"""Bind exact offline, public compatibility and saved-only diagnostic receipts."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AID=ROOT.name

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    path=ROOT/'selected-draft-execution-manifest.json'
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        folder=ROOT/'selected-proofs'/suffix
        relative=f'selected-proofs/{suffix}/'
        proof=json.loads((folder/'compatibility.json').read_text())
        if proof['case_id']!=case or proof['construction_sha256']!=entry['construction_sha256']:
            raise ValueError('Stale selected compatibility proof')
        offline=folder/'offline.log';compat=folder/'compatibility.json'
        entry['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-draft-execution-manifest.json --case {case} --output .runtime-work/c276263-selected-offline-{suffix}-v4 --python $PWD/.venv-cpu/bin/python',
                          'exit_code':0,'log':relative+'offline.log','log_sha256':sha(offline),
                          'construction_sha256':entry['construction_sha256']}
        entry['compatibility']={'receipt':relative+'compatibility.json','sha256':sha(compat),
                                'log':relative+'public-analysis.log'}
        entry['negative']={'log':relative+'negative-analysis.log'}
        entry['saved_cpu_diagnostic']={'receipt':relative+'saved-processing.json',
                                       'sha256':sha(folder/'saved-processing.json'),
                                       'scope':'synthetic source-shaped recorded-only processing; no physical or legal acceptance'}
        entry['post_capture']={
            'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
            'feedback_command':'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'recorded_only':True,'test_exit_code':0,
            'test_log':relative+'saved-processing.json',
            'test_log_sha256':sha(folder/'saved-processing.json')}
        attempt=f'.runtime-work/c276263-saved-attempt-{suffix}-v2' if suffix=='probe_a' else f'.runtime-work/c276263-saved-attempt-{suffix}-v1'
        positive=f'.venv-cpu/bin/python -B work/{AID}/native/delivery_audit.py --case {case} --attempt {attempt} --saved work/{AID}/{relative}saved-processing.json --fixture'
        entry['delivery_acceptance']={
            'case_id':case,'sets':['full-train'],
            'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
            'script':'native/delivery_audit.py','script_sha256':sha(ROOT/'native/delivery_audit.py'),
            'command':positive,'test_exit_code':0,
            'test_log':relative+'delivery-positive.log','test_log_sha256':sha(folder/'delivery-positive.log'),
            'negative_command':positive+' --reject-frame-join',
            'negative_exit_code':1,'negative_expected_error':'Original frame join differs at 599',
            'negative_log':relative+'delivery-negative.log','negative_log_sha256':sha(folder/'delivery-negative.log'),
            'production_command':f'.venv-cpu/bin/python -B work/{AID}/native/delivery_audit.py --case {case} --attempt "$ATTEMPT_DIR" --saved "$SAVED_RECEIPT"'}
        physical=folder/'physical/proof.json'
        entry['physical_preparation']={'receipt':relative+'physical/proof.json',
                                       'sha256':sha(physical)}
        for candidate in entry['candidates']:
            if candidate['id']!='fallback1':raise ValueError('Unexpected candidate')
            receipt=folder/'fallback1-compatibility.json'
            checked=json.loads(receipt.read_text())
            if (checked['case_id']!=case or checked['candidate_id']!='fallback1' or
                    checked['construction_sha256']!=candidate['construction_sha256']):
                raise ValueError('Stale fallback compatibility proof')
            candidate['offline']={
                'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-draft-execution-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c276263-fallback-offline-{suffix[-1]} --python $PWD/.venv-cpu/bin/python',
                'exit_code':0,'construction_sha256':candidate['construction_sha256'],
                'log':relative+'fallback1-offline.log',
                'log_sha256':sha(folder/'fallback1-offline.log')}
            candidate['compatibility']={
                'receipt':relative+'fallback1-compatibility.json','sha256':sha(receipt),
                'log':relative+'fallback1-compatibility-analysis.log',
                'negative_log':relative+'fallback1-negative-analysis.log'}
        runner='runner.py'
        entry['acquisition']={
            'kin.position':{'entrypoint':runner,'method':'ego.get_transform after each Native tick','evidence':'native-rows.jsonl original center, footprint and capture/evidence.jsonl'},
            'kin.velocity':{'entrypoint':runner,'method':'ego.get_velocity after each Native tick','evidence':'native-rows.jsonl speed and trace.jsonl velocity'},
            'sig.headlamp':{'entrypoint':runner,'method':'ego.get_light_state after each Native tick','evidence':'native-rows.jsonl original lamp bits plus source-hashed pixel review'},
            'drv.standing_or_parked':{'entrypoint':runner,'method':'handbrake control, original pose and separate activity review','evidence':'native-rows.jsonl and parking-activity-review.json'},
            'rel.occupies':{'entrypoint':runner,'method':'ego.bounding_box.get_world_vertices and parking waypoint','evidence':'native-rows.jsonl original footprint and curb lane'}}
    manifest['comparison_audit']={
        'comparison_id':AID+'__comparison',
        'script':'native/audit_saved_pair.py',
        'script_sha256':sha(ROOT/'native/audit_saved_pair.py'),
        'positive_log':'native/saved-pair-positive.log',
        'positive_log_sha256':sha(ROOT/'native/saved-pair-positive.log'),
        'negative_log':'native/saved-pair-negative.log',
        'negative_log_sha256':sha(ROOT/'native/saved-pair-negative.log'),
        'negative_expected_error':'Observed beam contrast missing',
        'diagnostic_only':True}
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
