"""Retain compact evidence from the eight reproducible synthetic package runs."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FILES=('compatibility.json','analysis-report.json','result.json',
       'source-0.json','source-1.json',
       'source-2.json','source-3.json','final-decode.json',
       'exception-d-source-manifest.json','duty-assignment.json')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    index={}
    for response in ('duty','routine'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            proof=json.loads((HERE/f'exception-d-package-{response}-{candidate}.json').read_text())
            output=ROOT/proof['output_root'];fixture=ROOT/proof['source_root']
            target=HERE/'draft-exception-d-exact-cases'/('exception_d_'+response)/candidate/'package-proof'
            target.mkdir(exist_ok=True)
            for name in FILES:shutil.copyfile(output/name,target/name)
            shutil.copyfile(output/'compatibility-analysis.log',target/'analysis.log')
            negative=output.parent/'negative.log'
            shutil.copyfile(negative,target/'negative.log')
            source=HERE/'draft-exception-d-cases'/response/candidate/'source-rows.jsonl'
            assert json.loads((target/'analysis-report.json').read_text())['source_scope']=='synthetic_cpu_fixture'
            assert sha(source)==sha(fixture/'exception_d_native_samples.jsonl')
            record={'format':'c10052-exception-d-durable-package-receipt-v1',
                    'case_id':proof['case_id'],'candidate_id':candidate,
                    'source_rows_sha256':sha(source),
                    'fixture_source_manifest_sha256':sha(fixture/'exception-d-source-manifest.json'),
                    'fixture_duty_assignment_sha256':sha(fixture/'duty-assignment.json'),
                    'files':{name:sha(target/name) for name in FILES+('analysis.log','negative.log')},
                    'accepted':False,'selected':False,'original_native_capture_executed':False}
            (target/'durable-receipt.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
            index[response+'-'+candidate]=sha(target/'durable-receipt.json')
            print(response,candidate,index[response+'-'+candidate])
    (HERE/'exception-d-package-durable-index.json').write_text(json.dumps({
        'format':'c10052-exception-d-package-durable-index-v1',
        'source_kind':'synthetic_cpu_fixture','accepted':False,'receipts':index},
        indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
