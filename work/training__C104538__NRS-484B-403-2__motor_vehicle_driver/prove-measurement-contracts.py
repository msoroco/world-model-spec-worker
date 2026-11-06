"""Pinned validator and saved positive/negative for both unselected cases."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate,verify_report


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    plan=json.loads((HERE/'case-plan.json').read_text())
    analysis=(HERE/'native/finalize.py').read_text()
    records=[]
    for suffix,fixture_name in (('witness_1','straight'),('witness_2','u_turn')):
        case_id=HERE.name+'__'+suffix
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-403-2',
                'source':'NRS 484B.403(2)','output_key':'signed_u_turn',
                'method':'measure_signed_u_turn','value_type':'object','kind':'measured',
                'inputs':['native_samples.jsonl','video_frames.jsonl','sign-review.json',
                          'pixel_review.jsonl','approach.mkv']}],
            'negative':{'remove':['native_samples.jsonl'],
                'error_contains':'Missing required source: native_samples.jsonl'}}
        contract_path=HERE/('draft-measurement-contract-'+suffix+'.json')
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        validate(contract,plan['requirement_dispositions'],analysis,case_id)
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c104538-u-turn-contract-') as temp:
            folder=Path(temp)
            source=HERE/'draft-u-turn-saved'/fixture_name
            for name in ('native_samples.jsonl','video_frames.jsonl','sign-review.json','pixel_review.jsonl'):
                shutil.copyfile(source/name,folder/name)
            shutil.copyfile(source/'approach-video-fixture.txt',folder/'approach.mkv')
            result=subprocess.run([sys.executable,str(HERE/'native/finalize.py'),
                '--attempt',str(folder),'--output',str(folder/'analysis-report.json')],
                capture_output=True,text=True)
            if result.returncode:raise RuntimeError(result.stderr)
            report=json.loads((folder/'analysis-report.json').read_text())
            verify_report(contract,report,folder)
            (folder/'native_samples.jsonl').unlink()
            failure=subprocess.run([sys.executable,str(HERE/'native/finalize.py'),
                '--attempt',str(folder),'--output',str(folder/'negative-report.json')],
                capture_output=True,text=True)
            if failure.returncode==0 or contract['negative']['error_contains'] not in failure.stderr:
                raise AssertionError('Missing-source negative did not reject')
            records.append({'case_id':case_id,'contract_sha256':sha(contract_path),
                'observed_u_turn':report['measurements']['signed_u_turn']['value']['u_turn_within_governed_region_observed'],
                'positive_report_verified':True,'missing_source_rejected':True})
    return {'passed':True,'records':records,'selected':False,'native_executed':False,
            'scope':'synthetic saved input and pinned contract validation only'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
