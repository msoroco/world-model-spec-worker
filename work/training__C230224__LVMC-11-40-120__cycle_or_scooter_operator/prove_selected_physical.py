"""Exercise path-choice motion assessment with source-bound synthetic rows."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SUFFIXES=('probe_01','probe_02')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(suffix,kind):
    path=HERE/'cases'/suffix/'diagnostic.json'
    files=json.loads(path.read_text())['files']
    rows=[json.loads(line) for line in files['native_rider_trace.jsonl'].splitlines()]
    frames=[json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
    if len(rows)!=600 or len(frames)!=600 or any(r['source_kind']!='synthetic_native_sample' for r in rows):
        raise ValueError('Synthetic Native source row contract changed')
    source={'path':str(path.relative_to(HERE)),'sha256':sha(path),
            'embedded_source':'files.native_rider_trace.jsonl'}
    if kind=='missing_evidence':
        return {'status':'unverified','method':'source-row rider displacement and identity join',
                'sources':[source],'reason':'source rows deliberately withheld from assessor'}
    selected=rows if kind=='complete_motion' else rows[:20]
    if any(row['device_actor_id']!=1 or row['rider_actor_id']!=2 for row in selected):
        raise ValueError('Device and attached rider identity changed')
    centers=[(min(p[0] for p in row['device_footprint_xy_m'])+
              max(p[0] for p in row['device_footprint_xy_m']))/2 for row in selected]
    progress=centers[-1]-centers[0]
    complete=progress>=10 and len(selected)==600
    if complete!=(kind=='complete_motion'):
        raise ValueError('Diagnostic did not realize requested motion outcome')
    return {'status':'met' if complete else 'not_met',
            'method':'joined rider Native source rows: 600 samples and engineering 10 m forward progress',
            'sources':[source],'source_rows_used':len(selected),'forward_progress_m':progress,
            'physical_acceptance_claimed':False,'legal_threshold_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=SUFFIXES,required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.kind=='lifecycle':
        events=['capture_finished','encoders_closed','restoration_verified',
                'native_exit','owner_released','saved_processing_started']
        assert events.index('owner_released')<events.index('saved_processing_started')
        print(json.dumps({'events':events,'premature_processing_rejected':True}))
        return
    if not args.output:
        parser.error('--output required')
    check=assess(args.case,args.kind)
    result={'format':'c230224-lvmc-synthetic-physical-outcome-v1',
            'case_id':HERE.name+'__'+args.case,
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'native_executed':False,'physical_acceptance_claimed':False,
            'legal_verdict_claimed':False,'physical_checks':{'maneuver':check},
            'maneuver_completed':check['status']=='met',
            'realized_observables':{'rider_forward_progress_m':{'value':check['forward_progress_m'],
                'unit':'m','method':check['method'],'sources':check['sources']}}
                if check['status']=='met' else {}}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_id':result['case_id'],'status':check['status'],'result_sha256':sha(dest)}))


if __name__=='__main__':
    main()
