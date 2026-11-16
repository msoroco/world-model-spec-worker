"""CPU contract proof for sealing after cleanup, without simulated CARLA speed."""
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release


def rejected(fn,label):
    try:fn()
    except ValueError:return label
    raise AssertionError('Capture seal accepted '+label)


def prove():
    negatives=[]
    with tempfile.TemporaryDirectory() as temporary:
        attempt=Path(temporary)
        (attempt/'construction.json').write_text('{}\n')
        (attempt/'runner.py').write_text('# CPU contract stub\n')
        (attempt/'trace.jsonl').write_text('{}\n')
        (attempt/'video_frames.jsonl').write_text('{}\n')
        restoration={'restored':True}
        kwargs=dict(frames=240,restoration=restoration,errors=[],
                    encoder_exit_codes={'overview':0,'approach':0,
                        'reference_corner':0,'driver_reference':0})
        negatives.append(rejected(lambda:seal_capture(attempt,**{
            **kwargs,'restoration':{'restored':False}}),'unrestored-world'))
        negatives.append(rejected(lambda:seal_capture(attempt,**{
            **kwargs,'errors':['capture failed']}),'capture-error'))
        negatives.append(rejected(lambda:seal_capture(attempt,**{
            **kwargs,'encoder_exit_codes':{'overview':1}}),'encoder-error'))
        assert not (attempt/'capture-seal.json').exists()
        seal=seal_capture(attempt,**kwargs)
        assert seal['events']==['capture_finished','encoders_closed',
                                'restoration_verified']
        assert seal['frames']==240 and seal['physical_acceptance_claimed'] is False
        exit_receipt=record_native_exit(attempt)
        assert exit_receipt['event']=='native_exit'
        negatives.append(rejected(lambda:acknowledge_owner_release(
            attempt,attempt/'operator-owner-release.json',False),
            'unattested-owner-release'))
        assert not (attempt/'operator-owner-release.json').exists()
    return {'format':'c146314-capture-seal-cpu-contract-v1','passed':True,
            'native_seal_shape_checked':True,'native_exit_shape_checked':True,
            'negative_rejections':negatives,'original_carla_executed':False,
            'operator_owner_release_attested':False,
            'original_speed_claimed':False}


if __name__=='__main__':print(json.dumps(prove(),sort_keys=True))
