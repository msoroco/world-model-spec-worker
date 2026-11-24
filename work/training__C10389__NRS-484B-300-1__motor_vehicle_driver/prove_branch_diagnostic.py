"""CPU source meter proof over eight clearly synthetic branch fixtures."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent;BASE=HERE/'cases/branch-requests'
spec=importlib.util.spec_from_file_location('branch_diagnostic_finalize',HERE/'branch-diagnostic-finalize.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def main():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='c10389-branch-meter-',dir=HERE.parents[1]/'.runtime-work') as name:
        root=Path(name)
        for suffix in ('signal_red_stop','signal_green_proceed','officer_no_direction_stop','officer_directed_proceed'):
            for candidate in ('primary','fallback1'):
                bundle=BASE/(suffix if candidate=='primary' else suffix+'-'+candidate)
                target=root/(suffix+'-'+candidate);target.mkdir()
                for f in (bundle/'raw-fixture').iterdir():
                    if f.is_file():shutil.copyfile(f,target/f.name)
                shutil.copyfile(bundle/'config.json',target/'config.json')
                result=module.measure_branch_response(target)['value']
                expected_stop=suffix in ('signal_red_stop','officer_no_direction_stop')
                if expected_stop!=(result['stopped_before_frames']>=20):
                    raise ValueError('Branch diagnostic stop contrast differs')
                if not expected_stop and result['body_at_station_frames']==0:
                    raise ValueError('Branch diagnostic crossing absent')
                if suffix.startswith('signal_') and len(result['signal_states'])!=1:
                    raise ValueError('Signal source state absent')
                if suffix=='officer_directed_proceed' and result['officer_actor_frames']!=600:
                    raise ValueError('Directed officer actor source absent')
                checks.append({'suffix':suffix,'candidate':candidate,'value':result})
        damaged=root/'signal_red_stop-primary';mapping=damaged/'native-map-readback.json'
        data=json.loads(mapping.read_text());data['stop_landmark_readback']['type']='206';mapping.write_text(json.dumps(data)+'\n')
        try:module.measure_branch_response(damaged)
        except ValueError as exc:
            if str(exc)!='Branch diagnostic device source changed':raise
        else:raise AssertionError('Wrong Native signal type accepted')
    return {'format':'c10389-branch-diagnostic-meter-proof-v1','checks':checks,
            'wrong_signal_type_rejected':True,'synthetic_only':True,'legal_outcome_claimed':False}


if __name__=='__main__':
    proof=main();(BASE/'diagnostic-meter-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'positive_meters':len(proof['checks']),'negative_rejections':1}))
