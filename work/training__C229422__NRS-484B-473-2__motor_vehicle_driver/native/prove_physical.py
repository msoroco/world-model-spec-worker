"""Synthetic CPU check of parked-lamp source joins and capture ownership order.

No fixture establishes actual nighttime, lawful parking, optical realization, or a
legal verdict. The source review in a future Native attempt must do that work.
"""
import argparse
import hashlib
import json
from pathlib import Path

ORDER=['capture_finished','encoders_closed','restoration_verified',
       'native_exit','owner_released','saved_processing_started']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]


def lifecycle(events):
    if events!=ORDER:raise ValueError('saved processing precedes Native ownership closure')
    return True


def evaluate(attempt,kind):
    attempt=Path(attempt)
    config=json.loads((attempt/'config.json').read_text())
    trace_path=attempt/'parked-lamp-trace.jsonl';frame_path=attempt/'video_frames.jsonl'
    trace,frames=rows(trace_path),rows(frame_path)
    if len(trace)!=600 or len(frames)!=600 or any(a['video_frame']!=i or b['video_frame']!=i or a['native_frame']!=b['native_frame'] for i,(a,b) in enumerate(zip(trace,frames))):
        raise ValueError('synthetic source frame history incomplete')
    sources={'parked-lamp-trace.jsonl':sha(trace_path),'video_frames.jsonl':sha(frame_path)}
    review_path=attempt/'lamp-pixel-review.json'
    if kind=='missing_evidence':
        review=None;status='unverified';observables={}
    else:
        review=json.loads(review_path.read_text());sources['lamp-pixel-review.json']=sha(review_path)
        if review.get('case_id')!=config['case_id'] or len(review.get('optical_observations',[]))!=600:
            raise ValueError('pixel review differs from selected case')
        stopped=all(a['ego_speed_mps']<=0.1 for a in trace)
        pixels=review['optical_observations']
        modes={'depressed_low_beam':(True,False,False),
               'undepressed_high_beam':(False,True,False),
               'undepressed_high_beam_with_parking':(False,True,True)}
        expected=modes[config['mode']]
        selected=all((p['depressed_or_dimmed'],p['undepressed_headlamp'],p['cowl_or_parking_used'])==expected and p['lights_displayed'] for p in pixels)
        context=all(review.get(k) is True for k in ('lawfully_parked','highway','civil_night'))
        if kind=='complete_motion':status='met' if stopped and selected and context else 'not_met'
        elif kind=='incomplete_motion':
            # Remove the reviewed optical interval while retaining the trace.
            observed_pixels=[]
            status='not_met' if len(observed_pixels)!=600 else 'met'
        else:raise ValueError('unknown fixture kind')
        observables={'reviewed_lamp_frames':len(pixels),'stopped_frames':sum(a['ego_speed_mps']<=0.1 for a in trace),
                     'controlled_incomplete_mutation':kind=='incomplete_motion'}
    return {'case_id':config['case_id'],'fixture_kind':kind,'diagnostic_fixture':True,
            'provenance_kind':'synthetic_fixture','original_native_observed':False,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
            'physical_checks':{'maneuver':{'status':status,
                'method':'synthetic original-shaped parked trace, frame joins, optical review, and controlled missing/incomplete mutations',
                'sources':sources}},'maneuver_completed':status=='met','realized_observables':observables}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt');p.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence'))
    p.add_argument('--output');p.add_argument('--lifecycle',action='store_true');a=p.parse_args()
    if a.lifecycle:
        assert lifecycle(ORDER)
        try:lifecycle(ORDER[:-2]+[ORDER[-1],ORDER[-2]])
        except ValueError as error:print(str(error))
        else:raise AssertionError('premature saved processing accepted')
        print('capture ownership closure precedes saved processing')
    else:
        result=evaluate(a.attempt,a.kind)
        Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
        print(a.kind,result['physical_checks']['maneuver']['status'])
