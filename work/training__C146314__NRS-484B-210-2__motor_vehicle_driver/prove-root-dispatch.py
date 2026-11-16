"""CPU proof of both exact-case dispatches and rejection of stale selections."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import runner

ROOT=Path(__file__).resolve().parent


def rejected(manifest,label):
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'manifest.json'
        path.write_text(json.dumps(manifest))
        try:
            runner.check(path)
        except (ValueError,KeyError,StopIteration):
            return label
    raise AssertionError('Root dispatch accepted '+label)


def prove():
    source=json.loads((ROOT/'execution-manifest-unified-draft.json').read_text())
    positive=runner.check()
    assert positive['cases']==2 and positive['fallbacks']==6
    calls=[]
    exits=[]
    def recorded(command,**kwargs):
        calls.append(command)
        if 'materialize' in command:
            output=Path(command[command.index('--output')+1]);output.mkdir()
            (output/'config.json').write_text('{}\n')
            (output/'construction.json').write_text('{}\n')
            (output/'runner.py').write_text('# CPU stub\n')
        else:
            output=Path(command[command.index('--output-dir')+1])
            materialize=calls[-2]
            case=materialize[materialize.index('--case')+1]
            candidate=materialize[materialize.index('--candidate')+1]
            cfg=output/'config.json'
            (output/'native-capture-report.json').write_text(json.dumps({
                'case_id':case,'candidate_id':candidate,
                'config_sha256':hashlib.sha256(cfg.read_bytes()).hexdigest(),
                'requested_frames':240,'observed_frames':240,
                'error':None,'closure_failures':[],
                'lifecycle_events':['capture_finished','encoders_closed',
                                    'restoration_verified'],
                'restoration':{'restored':True}})+'\n')
            (output/'capture-seal.json').write_text(json.dumps({
                'format':'worker-sealed-capture','provenance_kind':'native',
                'events':['capture_finished','encoders_closed',
                          'restoration_verified'],
                'frames':240,'restoration':{'restored':True},
                'native_revision':{
                    'construction_sha256':runner.sha(output/'construction.json'),
                    'runner_sha256':runner.sha(output/'runner.py')}})+'\n')
    with tempfile.TemporaryDirectory() as temporary, patch.object(runner.subprocess,'run',recorded):
        for witness in ('reference','contrast'):
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                case=ROOT.name+'__'+witness
                exit_observation=runner.launch(case,candidate,
                    Path(temporary)/(witness+'-'+candidate),
                    '/operator/carla-python','localhost',2000)
                assert exit_observation['events']==['capture_finished','encoders_closed',
                    'restoration_verified','native_exit']
                assert exit_observation['operator_owner_release_attested'] is False
                assert exit_observation['saved_processing_started'] is False
                exits.append(exit_observation)
    assert len(calls)==16
    for materialize,capture in zip(calls[::2],calls[1::2]):
        assert 'materialize' in materialize and '--candidate' in materialize
        assert capture[0]=='/operator/carla-python' and capture[-2:]==['--port','2000']
    negatives=[]
    changed=copy.deepcopy(source);changed['cases'][0]['construction_sha256']='0'*64
    negatives.append(rejected(changed,'changed-primary-hash'))
    changed=copy.deepcopy(source);changed['cases'][1]['candidates']=changed['cases'][1]['candidates'][:2]
    negatives.append(rejected(changed,'missing-fallback'))
    changed=copy.deepcopy(source);changed['cases'][1]['case_id']=changed['cases'][0]['case_id']
    negatives.append(rejected(changed,'duplicate-case'))
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)
        case=ROOT.name+'__reference'
        def release_rejected(label):
            try:runner.record_native_exit_observation(output,case,'primary')
            except ValueError:return label
            raise AssertionError('Native exit observation accepted '+label)
        negatives.append(release_rejected('missing-capture-report'))
        (output/'config.json').write_text('{}\n')
        (output/'construction.json').write_text('{}\n')
        (output/'runner.py').write_text('# CPU stub\n')
        report={'case_id':case,'candidate_id':'primary',
            'config_sha256':runner.sha(output/'config.json'),
            'requested_frames':240,'observed_frames':240,'error':None,
            'closure_failures':[],
            'lifecycle_events':['capture_finished','encoders_closed',
                                'restoration_verified'],
            'restoration':{'restored':True}}
        path=output/'native-capture-report.json'
        (output/'capture-seal.json').write_text(json.dumps({
            'format':'worker-sealed-capture','provenance_kind':'native',
            'events':report['lifecycle_events'],'frames':240,
            'restoration':{'restored':True},
            'native_revision':{
                'construction_sha256':runner.sha(output/'construction.json'),
                'runner_sha256':runner.sha(output/'runner.py')}})+'\n')
        for label,change in (
            ('wrong-case',{'case_id':'other'}),
            ('changed-config',{'config_sha256':'0'*64}),
            ('incomplete-capture',{'observed_frames':239}),
            ('failed-encoder',{'closure_failures':[{'encoder':'failed'}]}),
            ('unrestored-world',{'restoration':{'restored':False}})):
            path.write_text(json.dumps({**report,**change})+'\n')
            negatives.append(release_rejected(label))
    return {'format':'c146314-root-dispatch-proof-v1','passed':True,
            'checked_cases':2,'checked_fallbacks':6,'materialize_and_capture_calls':len(calls),
            'mocked_native_exits':len(exits),
            'negative_rejections':negatives,'carla_executed':False,
            'physical_acceptance_claimed':False}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
