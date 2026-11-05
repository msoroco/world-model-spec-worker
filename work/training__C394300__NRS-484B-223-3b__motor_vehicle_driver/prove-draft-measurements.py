"""Exercise five draft measurement contracts on synthetic saved sources."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate,verify_report

spec=importlib.util.spec_from_file_location('center_lane_test',FOLDER/'native/test_measure_center_lane.py')
fixture=importlib.util.module_from_spec(spec)
sys.path.insert(0,str(FOLDER/'native'))
spec.loader.exec_module(fixture)


def run():
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    code=(FOLDER/'native/measure_saved.py').read_text()
    env=dict(os.environ)
    rows=[]
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        contract=json.loads((FOLDER/'draft-measurements'/(suffix+'-contract.json')).read_text())
        validate(contract,plan['requirement_dispositions'],code,case['case_id'])
        feet=fixture_distance(suffix)
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-measure-') as name:
            root=Path(name);fixture.fixture(root,feet*.3048)
            output=root/'analysis-report.json'
            command=[sys.executable,str(FOLDER/'native/measure_saved.py'),
                     '--attempt',str(root),'--output',str(output)]
            positive=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            if positive.returncode:raise RuntimeError(positive.stdout)
            report=json.loads(output.read_text())
            verified=verify_report(contract,report,root)
            relation=verified['center_lane_entry_to_turn_distance']['value']['threshold_relation']
            (root/'native_samples.jsonl').unlink()
            negative=subprocess.run([sys.executable,str(FOLDER/'native/measure_saved.py'),
                '--attempt',str(root),'--output',str(root/'negative-report.json')],
                text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            expected=contract['negative']['error_contains']
            if negative.returncode==0 or expected not in negative.stdout:
                raise RuntimeError('Missing-source rejection failed: '+negative.stdout)
            rows.append({'case_suffix':suffix,'commanded_distance_ft':feet,
                'measured_relation_in_synthetic_fixture':relation,
                'positive_exit_code':0,'negative_exit_code':negative.returncode,
                'negative_error_contains':expected,'contract_verified':True,
                'scope':'synthetic source-bound draft measurement; no Native physical or legal outcome'})
    return {'format':'c394300-3b-draft-measurement-proof-v1',
            'cases':rows,'selected_delivery_cases':0}


def fixture_distance(suffix):
    return {'witness_1':180,'witness_2':220,'numeric_1_0':199,
            'numeric_1_1':200,'numeric_1_2':201}[suffix]


if __name__=='__main__':print(json.dumps(run(),indent=2))
