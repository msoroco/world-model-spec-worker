"""Measured synthetic fallback trigger/mitigation checks."""
import json
from build import CASES, HERE, put


def trigger(saved, cfg, *, original_pixels=False, reversal_proven=False):
    return {'fallback1':cfg['requested_approach_speed_mps']>4.0,
            'fallback2':not original_pixels,
            'fallback3':saved['pre_turn_stationary_frames']<40 or not reversal_proven}


def prove():
    positives=negatives=0;details={}
    for suffix in CASES:
        saved={name:json.loads((HERE/'synthetic'/suffix/name/'saved.json').read_text())
               for name in ('primary','fallback1','fallback2','fallback3')}
        cfg={name:json.loads((HERE/'drafts'/suffix/name/'config.json').read_text())
             for name in saved}
        baseline=trigger(saved['primary'],cfg['primary'])
        if baseline!={'fallback1':True,'fallback2':True,'fallback3':True}:
            raise ValueError('Primary fallback predicates changed')
        if not cfg['fallback1']['requested_approach_speed_mps']<cfg['primary']['requested_approach_speed_mps'] or \
                cfg['fallback2']['camera_policy']!='elevated_overview' or \
                saved['fallback3']['pre_turn_stationary_frames']<40:
            raise ValueError('Fallback mitigation did not change measured request')
        positives+=1
        tests=[('fallback1',trigger(saved['fallback1'],cfg['fallback1'],original_pixels=True,reversal_proven=True)),
               ('fallback2',trigger(saved['primary'],cfg['primary'],original_pixels=True,reversal_proven=True)),
               ('fallback3',trigger(saved['fallback3'],cfg['fallback3'],original_pixels=True,reversal_proven=True))]
        for key,observed in tests:
            if observed[key]:raise ValueError('Switched-condition negative failed: '+key)
            negatives+=1
        details[suffix]={'primary_trigger':baseline,
                         'primary_stationary_frames':saved['primary']['pre_turn_stationary_frames'],
                         'fallback3_stationary_frames':saved['fallback3']['pre_turn_stationary_frames']}
    result={'format':'c111662-4033-trigger-proof-v1','positive_count':positives,
            'negative_count':negatives,'cases':details,'synthetic_only':True,'delivery_ready':False}
    put(HERE/'trigger-proof.json',result)
    return result


if __name__=='__main__':print(json.dumps(prove()))
