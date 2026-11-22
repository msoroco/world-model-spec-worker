"""Reprocess the selected control primary from saved synthetic sources."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'runtime/pipeline'), str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.saved_processing import run

MANIFEST = HERE/'current-runtime-reproof-manifest.json'
VALIDATOR = ROOT/'.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'
OUTPUT = ROOT/'.runtime-work/c110812-current-reproof-control-primary-saved'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    document=json.loads(MANIFEST.read_text())
    entry=next(x for x in document['cases'] if x['case_id'].endswith('__control'))
    if document['runtime_manifest_sha256'] != sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'):
        raise ValueError('Selected reproof manifest is stale')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    fixture=OUTPUT/'fixture'
    source=materialize(ROOT,ROOT/entry['fixture_recipe'],fixture)
    attempt=OUTPUT/'attempt'
    materialize_case(MANIFEST,entry['case_id'],attempt,fixture,'primary')
    result=run(MANIFEST,entry['case_id'],attempt,OUTPUT/'output',
               ROOT/'runtime/pipeline/library',VALIDATOR)
    if not result.get('passed') or not result.get('recorded_only') or result.get('missing_evidence'):
        raise ValueError('Current-runtime saved processing did not pass')
    if result['analysis_revision']['runtime_manifest_sha256'] != document['runtime_manifest_sha256']:
        raise ValueError('Saved result binds another runtime')
    if result['analysis_revision']['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Saved result binds another construction')
    return {'format':'c110812-current-runtime-control-primary-saved-v1',
            'case_id':entry['case_id'],'candidate_id':'primary',
            'runtime_manifest_sha256':document['runtime_manifest_sha256'],
            'construction_sha256':entry['construction_sha256'],
            'recorded_only':True,'passed':True,'source':source,'result':result}


if __name__=='__main__':
    print(json.dumps(main(),indent=2,sort_keys=True))
