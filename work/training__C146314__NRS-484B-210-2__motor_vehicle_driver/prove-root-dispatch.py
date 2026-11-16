"""CPU proof of both exact-case dispatches and rejection of stale selections."""
import copy
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
    def recorded(command,**kwargs):
        calls.append(command)
    with tempfile.TemporaryDirectory() as temporary, patch.object(runner.subprocess,'run',recorded):
        for witness in ('reference','contrast'):
            for candidate in ('primary','fallback1','fallback2','fallback3'):
                case=ROOT.name+'__'+witness
                runner.launch(case,candidate,Path(temporary)/(witness+'-'+candidate),
                              '/operator/carla-python','localhost',2000)
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
    return {'format':'c146314-root-dispatch-proof-v1','passed':True,
            'checked_cases':2,'checked_fallbacks':6,'materialize_and_capture_calls':len(calls),
            'negative_rejections':negatives,'carla_executed':False,
            'physical_acceptance_claimed':False}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
