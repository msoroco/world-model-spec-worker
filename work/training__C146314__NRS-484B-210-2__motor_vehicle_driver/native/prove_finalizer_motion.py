"""CPU proof of result status mapping; no velocity or recording is invented."""
import json

from finalize_selected import motion_fields


def rejected(fn,label):
    try:fn()
    except ValueError:return label
    raise AssertionError('Finalizer motion mapping accepted '+label)


def prove():
    sources={'native-raw-actors.jsonl':'0'*64}
    synthetic=motion_fields('synthetic_native_sample',None,sources)
    assert synthetic['check']['status']=='unverified'
    assert synthetic['provenance_kind']=='synthetic_local_diagnostic'
    outputs={}
    for status in ('met','not_met','unverified'):
        review={'source_kind':'original_native','status':status,
                'maneuver_completed':status=='met',
                'method':'source-derived right-side pass motion',
                'sources':sources,'missing_evidence':[]}
        mapped=motion_fields('original_native',review,sources)
        assert mapped['check']['status']==status
        assert mapped['maneuver_completed']==(status=='met')
        assert mapped['provenance_kind']=='native'
        assert mapped['check']['legal_verdict_claimed'] is False
        outputs[status]=mapped['maneuver_completed']
    negatives=[
        rejected(lambda:motion_fields('original_native',None,sources),'missing-review'),
        rejected(lambda:motion_fields('original_native',{
            'source_kind':'synthetic_native_sample','status':'met',
            'maneuver_completed':True,'method':'mock','sources':sources},sources),
            'synthetic-as-original'),
        rejected(lambda:motion_fields('original_native',{
            'source_kind':'original_native','status':'met',
            'maneuver_completed':False,'method':'mock','sources':sources},sources),
            'completion-status-mismatch')]
    return {'format':'c146314-finalizer-motion-contract-v1','passed':True,
            'hypothetical_status_mapping':outputs,'negative_rejections':negatives,
            'original_carla_executed':False,'physical_acceptance_claimed':False,
            'original_speed_claimed':False,'legal_safety_verdict':None}


if __name__=='__main__':print(json.dumps(prove(),sort_keys=True))
