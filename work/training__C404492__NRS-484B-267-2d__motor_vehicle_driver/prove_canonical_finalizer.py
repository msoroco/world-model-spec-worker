"""CPU check for canonical saved channels and fail-closed case sources."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from finalize import finalize_attempt
from measure_emergency import AID, CAMERAS, rows
from prove_emergency import fixture
from worker_exchange.measurement_contract import validate, verify_report


def reject(attempt, output):
    try:
        finalize_attempt(attempt, output)
    except ValueError:
        return
    raise AssertionError('Invalid saved attempt accepted')


def main():
    folder=Path(__file__).resolve().parent
    plan=json.loads((folder/'case-plan.json').read_text())
    with tempfile.TemporaryDirectory(prefix='c404492-canonical-',dir=os.environ['TMPDIR']) as temp:
        for suffix,overlap in (('controlled_1',False),('controlled_2',True)):
            bundle=json.loads((folder/f'draft-emergency/{suffix}/primary/construction.json').read_text())
            config=next(json.loads(f['content']) for f in bundle['files'] if f['path']=='config.json')
            analysis_code=next(f['content'] for f in bundle['files'] if f['path']=='finalize.py')
            contract=json.loads((folder/f'measurement-contracts/{suffix}.json').read_text())
            validate(contract,plan['requirement_dispositions'],analysis_code,AID+'__'+suffix)
            root=Path(temp)/suffix
            fixture(root,overlap)
            context=root/'emergency_context.json'
            value=json.loads(context.read_text())
            value['case_id']=AID+'__'+suffix
            context.write_text(json.dumps(value)+'\n')
            (root/'config.json').write_text(json.dumps(config)+'\n')
            (root/'construction.json').write_text(json.dumps(bundle)+'\n')
            for name in CAMERAS:
                video=root/(name+'.mkv')
                run=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                    'color=c=black:s=16x16:r=20','-frames:v','600','-c:v','ffv1',str(video)],
                    capture_output=True,text=True)
                if run.returncode:
                    raise AssertionError('Diagnostic camera generation failed: '+run.stderr[-300:])
            report=finalize_attempt(root,root/'analysis-report.json')
            assert 'per_frame_geometry' in verify_report(contract,report,root)
            assert report['case_id']==AID+'__'+suffix
            result=json.loads((root/'result.json').read_text())
            assert result['case_id']==report['case_id'] and result['accepted'] is False
            assert result['target_checks'][0]['matched'] is True
            assert result['provenance_kind']=='synthetic_local_diagnostic'
            for item in result['recording_evidence']:
                reference=root/item['reference']
                if reference.suffix=='.jsonl':
                    data=rows(reference)
                    assert len(data)==600 and data[0]['time_s']==0
                else:
                    data=json.loads(reference.read_text())
                    assert data['emergency_context']['emergency_vehicle_authorized'] is True
                    assert data['officer_direction_context'] is False
            reject(root,root/'another-report.json')
        missing=Path(temp)/'missing'
        fixture(missing,False)
        bundle=json.loads((folder/'draft-emergency/controlled_1/primary/construction.json').read_text())
        config=next(json.loads(f['content']) for f in bundle['files'] if f['path']=='config.json')
        (missing/'config.json').write_text(json.dumps(config)+'\n')
        (missing/'construction.json').write_text(json.dumps(bundle)+'\n')
        reject(missing,missing/'analysis-report.json')
        false_original=Path(temp)/'false-original'
        fixture(false_original,False)
        (false_original/'config.json').write_text(json.dumps(config)+'\n')
        (false_original/'construction.json').write_text(json.dumps(bundle)+'\n')
        claim=false_original/'emergency_context.json'
        value=json.loads(claim.read_text())
        value['review_kind']='original_source_review'
        claim.write_text(json.dumps(value)+'\n')
        for name in CAMERAS:
            (false_original/(name+'.mkv')).write_bytes(b'not-original-media')
        reject(false_original,false_original/'analysis-report.json')
        print(json.dumps({'case_ids':[AID+'__controlled_1',AID+'__controlled_2'],
            'channels_per_case':7,'frames_per_channel':600,'preexisting_result_rejected':True,
            'missing_video_rejected':True,'false_original_rejected':True,
            'public_measurement_contract_passed':True,
            'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
