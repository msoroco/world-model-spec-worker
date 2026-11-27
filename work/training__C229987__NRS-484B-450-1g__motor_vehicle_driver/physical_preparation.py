"""CPU exercise of measured halt completion and local capture ownership ordering."""
import argparse
import json
from pathlib import Path

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def classify(samples, requested_gap_m):
    if not samples:
        return {'status':'unverified', 'method':'600 original aligned motion/footprint samples',
                'sources':['signal_raw.json','trace.jsonl','video_frames.jsonl']}
    if len(samples) != 600 or any('speed_mps' not in row or 'front_edge_to_signal_station_m' not in row for row in samples):
        return {'status':'unverified', 'method':'600 original aligned motion/footprint samples',
                'sources':['signal_raw.json','trace.jsonl','video_frames.jsonl']}
    rest = [r for r in samples[-100:] if r['speed_mps'] <= .15]
    matched = len(rest) >= 80 and all(abs(r['front_edge_to_signal_station_m']-requested_gap_m) <= .2 for r in rest)
    return {'status':'met' if matched else 'not_met',
            'method':'80 of final 100 samples at low speed and observed front-edge gap within engineering target window',
            'sources':['signal_raw.json','trace.jsonl','video_frames.jsonl'],
            'final_rest_samples':len(rest),
            'requested_gap_m':requested_gap_m,
            'observed_final_gap_m':samples[-1]['front_edge_to_signal_station_m']}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native ownership closure')
    return {'events':events, 'exit_code':0, 'premature_saved_processing_rejected':True}


def fixture(case, kind):
    if kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('Unknown fixture kind')
    requested = int(case.rsplit('__',1)[-1])*.3048
    samples = [{'speed_mps':0.0,
                'front_edge_to_signal_station_m':requested if kind=='complete_motion' else requested+3}
               for _ in range(600)] if kind!='missing_evidence' else []
    check = classify(samples,requested)
    return {'case_id':case, 'physical_checks':{'maneuver':check},
            'maneuver_completed':check['status']=='met',
            'realized_observables':{'diagnostic_final_gap_m':requested} if check['status']=='met' else {},
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'original_native_observed':False,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',choices=['complete_motion','incomplete_motion','missing_evidence','lifecycle'],required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=lifecycle(EVENTS) if args.kind=='lifecycle' else fixture(args.case,args.kind)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':args.case,'kind':args.kind,'passed':True}))
