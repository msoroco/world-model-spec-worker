"""CPU proof of Native capture ownership closure and failure ordering."""
import json

import capture
from audit_delivery import verify_capture_closure


class Pipeline:
    def __init__(self, trace, fail=False):self.trace=trace;self.fail=fail
    def close(self, confirmed):
        self.trace.append(('capture.close',confirmed))
        if self.fail:raise RuntimeError('pipeline close failed')


class Input:
    def __init__(self, trace):self.trace=trace
    def close(self):self.trace.append(('encoder.stdin.close',))


class Process:
    def __init__(self, trace, exit_code=0):
        self.trace=trace;self.stdin=Input(trace);self.exit_code=exit_code
    def wait(self, timeout):
        self.trace.append(('encoder.wait',timeout));return self.exit_code


class Log:
    def __init__(self, trace):self.trace=trace
    def close(self):self.trace.append(('encoder.log.close',))


class Actor:
    type_id='sensor.camera.rgb';is_listening=True
    def __init__(self, trace):self.trace=trace
    def stop(self):self.trace.append(('sensor.stop',))
    def destroy(self):self.trace.append(('actor.destroy',))


def scenario(*,capture_ok=True,encoder_ok=True,restore_ok=True):
    trace=[]
    def restore(client,saved):
        trace.append(('world.restore',))
        if not restore_ok:raise RuntimeError('restore readback differs')
        return {'restored':True}
    result=capture.close_capture(
        Pipeline(trace),{'overview':Process(trace,0 if encoder_ok else 1)},
        {'overview':Log(trace)},[Actor(trace)],True,object(),object(),restore,
        capture_ok)
    return result,trace


def prove():
    positive,trace=scenario()
    assert positive['events']==[
        'capture_finished','encoders_closed','restoration_verified']
    assert not positive['failures'] and positive['restoration']=={'restored':True}
    assert trace==[
        ('capture.close',True),('encoder.stdin.close',),('encoder.wait',180),
        ('encoder.log.close',),('sensor.stop',),('actor.destroy',),
        ('world.restore',)]
    negatives=[]
    for name,options in (
        ('capture_failed',{'capture_ok':False}),
        ('encoder_failed',{'encoder_ok':False}),
        ('restore_failed',{'restore_ok':False})):
        result,trace=scenario(**options)
        assert result['events']!=positive['events']
        assert 'restoration_verified' not in result['events']
        assert ('world.restore',) in trace
        if name!='capture_failed':assert result['failures']
        negatives.append(name)
    report={'case_id':'test-case','candidate_id':'primary',
            'observed_frames':240,'error':None,'closure_failures':[],
            'lifecycle_events':positive['events'],
            'restoration':positive['restoration']}
    verify_capture_closure(report,'test-case','primary')
    for name,change in (
        ('wrong_case',{'case_id':'other'}),
        ('missing_frame',{'observed_frames':239}),
        ('early_processing',{'lifecycle_events':['capture_finished']}),
        ('unrestored_world',{'restoration':{'restored':False}})):
        altered={**report,**change}
        try:verify_capture_closure(altered,'test-case','primary')
        except ValueError:negatives.append(name)
        else:raise AssertionError('Delivery closure accepted '+name)
    return {'format':'c146314-native-closure-proof-v1','passed':True,
            'events':positive['events'],'negative_rejections':negatives,
            'original_carla_executed':False,'saved_processing_started':False}


if __name__=='__main__':print(json.dumps(prove(),sort_keys=True))
