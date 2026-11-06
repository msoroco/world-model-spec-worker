"""Two 480-frame bicycle/motorist CPU positives and source-bound negatives."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
NATIVE=FOLDER/'native'
OUT=ROOT/'.runtime-work/c111294-interaction-proof'
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.measurement_contract import validate,verify_report

spec=importlib.util.spec_from_file_location('cycle_measure',NATIVE/'measure.py')
measurement=importlib.util.module_from_spec(spec);spec.loader.exec_module(measurement)

def reject(source,expected_hash,road,part):
    try:measurement.measure(source,expected_hash,road)
    except ValueError as error:
        if part not in str(error):raise AssertionError(f'Wrong rejection: {error}') from error
    else:raise AssertionError('Damaged source accepted')

def main():
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    base=json.loads((NATIVE/'measurement-contract.json').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for case in measurement.CASES:
        folder=OUT/case
        if folder.exists():shutil.rmtree(folder)
        folder.mkdir()
        road=folder/'road.xodr';shutil.copyfile(NATIVE/'road.xodr',road)
        original=measurement.synthetic(case,measurement.sha(road))
        source=folder/'interaction.json'
        source.write_text(json.dumps(original,sort_keys=True)+'\n')
        expected=measurement.sha(source)
        value=measurement.measure(source,expected,road)
        if case=='witness_1':assert not value['motorist_braked'] and value['motor_braking_frames']==0
        else:assert value['motorist_braked'] and value['motor_braking_frames']==175
        assert not value['intent_physically_verified'] and not value['legal_interference_claimed']
        contract=dict(base);contract['case_id']=plan['assignment_id']+'__'+case
        contract_path=NATIVE/('measurement-contract-'+case+'.json')
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        validate(contract,plan['requirement_dispositions'],(NATIVE/'measure.py').read_text(),contract['case_id'])
        report={'measurements':{'bicycle_motorist_interaction':{'method':'measure','value':value,
            'sources':{'interaction.json':expected,'road.xodr':measurement.sha(road)}}}}
        verify_report(contract,report,folder)
        source.unlink();reject(source,expected,road,'Missing required source')
        source.write_text(json.dumps(original,sort_keys=True)+'\n')
        changed=dict(original);changed['frames']=original['frames'][:-1]
        source.write_text(json.dumps(changed)+'\n');reject(source,expected,road,'missing or changed')
        reject(source,measurement.sha(source),road,'Full 480-frame')
        changed=dict(original);changed['frames']=[dict(row) for row in original['frames']]
        changed['frames'][200]=dict(changed['frames'][200]);changed['frames'][200]['bicycle']=dict(changed['frames'][200]['bicycle'])
        changed['frames'][200]['bicycle']['class']='moped'
        source.write_text(json.dumps(changed)+'\n');reject(source,measurement.sha(source),road,'class source differs')
        changed=dict(original);changed['intent_physically_verified']=True
        source.write_text(json.dumps(changed)+'\n');reject(source,measurement.sha(source),road,'intent claim differs')
        source.write_text(json.dumps(original,sort_keys=True)+'\n')
        broken=dict(report);broken['measurements']={'bicycle_motorist_interaction':dict(report['measurements']['bicycle_motorist_interaction'])}
        broken['measurements']['bicycle_motorist_interaction']['sources']={'road.xodr':measurement.sha(road)}
        try:verify_report(contract,broken,folder)
        except ValueError as error:assert 'Measurement sources differ' in str(error)
        else:raise AssertionError('Missing source hash passed contract')
        assert measurement.measure(source,expected,road)==value
        results[case]={'source_sha256':expected,'motor_braking_frames':value['motor_braking_frames'],
            'minimum_clearance_m':value['minimum_actor_body_clearance_m'],
            'bicycle_intersection_first_frame':value['bicycle_intersection_first_frame'],
            'motor_intersection_first_frame':value['motor_intersection_first_frame']}
    print(json.dumps({'passed':True,'frames_per_case':480,'cases':results,'negative_checks_per_case':5,
        'physical_behavior_or_intent_claimed':False},sort_keys=True))

if __name__=='__main__':main()
