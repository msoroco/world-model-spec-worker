"""Independent original Native signal-approach source and completion audit."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source','all_participants','time_join','full_video_decode',
          'actual_pixels','physical_completion')
REQUIRED = ('signal_raw.json','context-survey.json','video_frames.jsonl',
            'trace.jsonl','capture/evidence.jsonl','road.xodr')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root,name):
    target=(root/name).resolve()
    if root.resolve() not in target.parents or not target.is_file():
        raise ValueError('Missing original source: '+name)
    return target


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s]


def check_result(result,case):
    if (result.get('case_id')!=case or result.get('provenance_kind')!='native' or
            result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original signal-approach motion or sustained rest incomplete')
    measured=result.get('measured_values',{})
    if len(measured.get('frames',[]))!=600 or measured.get('stationary_sample_count',0)<80:
        raise ValueError('Missing original signal-approach footprint measurement')
    expected={'ego_pose','stop_distance_on_signal_approach','kin.speed','dev.traffic_signal',
              'dev.position','rel.centre_distance','drv.approaching','rel.occupies',
              'drv.standing_or_parked','drv.forced_halt','dev.human_direction'}
    if not expected <= {item.get('name') for item in result.get('recording_evidence',[])}:
        raise ValueError('Missing signal, motion or exception source channel')
    if result.get('accepted') is not False or result.get('physical_acceptance_claimed') is True:
        raise ValueError('Saved finalizer preaccepted original outcome')


def check_review(review,case,sources):
    if (review.get('case_id')!=case or review.get('review_kind')!='original_source_review' or
            not review.get('independent_reviewer')):
        raise ValueError('Missing independent original signal review')
    for key in ('highway_status','official_signal_status','halt_purpose',
                'other_traffic_conflict','applicable_law_direction',
                'officer_direction','device_direction'):
        if review.get(key) is None:
            raise ValueError('Original signal or exception context unreviewed: '+key)
    if not review.get('actual_pixels_reviewed') or not review.get('approach_geometry_reviewed'):
        raise ValueError('Original signal pixels or approach geometry unreviewed')
    if review.get('signal_raw_sha256')!=sources['signal_raw.json'] or review.get('road_sha256')!=sources['road.xodr']:
        raise ValueError('Original signal review source hash differs')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt=Path(args.attempt).resolve();operations=Path(args.operations).resolve();output=Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path=source(attempt,'result.json');result=json.loads(result_path.read_text())
    check_result(result,args.case)
    sources={name:sha(source(attempt,name)) for name in REQUIRED}
    check_review(json.loads(source(attempt,args.review).read_text()),args.case,sources)
    frame_map=rows(source(attempt,'video_frames.jsonl'))
    trace=rows(source(attempt,'trace.jsonl'))
    raw=json.loads(source(attempt,'signal_raw.json').read_text())
    motion=raw.get('frames',[])
    if len(frame_map)!=600 or len(trace)!=600 or len(motion)!=600:
        raise ValueError('Original signal frame count differs')
    for i,(frame,row,sample) in enumerate(zip(frame_map,trace,motion)):
        if (frame.get('video_frame')!=i or row.get('frame')!=frame.get('carla_frame') or
                sample.get('native_frame')!=frame.get('carla_frame') or
                abs(row['time_s']-frame['time_s'])>1e-6 or
                abs(sample['time_s']-frame['time_s'])>1e-6):
            raise ValueError('Original signal source time join differs')
    report=json.loads(source(attempt,'analysis-report.json').read_text())
    for key in ('stopping_context','signal_approach_distance','official_signal_context'):
        measured=report.get('measurements',{}).get(key,{})
        if measured.get('method')!='measure_signal_approach' or measured.get('sources')!=sources:
            raise ValueError('Original signal measurement source hash differs: '+key)
    mapping_sha=sha(source(attempt,'video_frames.jsonl'))
    video=source(attempt,args.video)
    decode=output.with_name('source-decode-'+args.case.rsplit('__',1)[-1]+'.json')
    media.audit(video,600,mapping_sha256=mapping_sha,receipt=decode)
    verified=media.verify_receipt(video,decode,600,mapping_sha256=mapping_sha)
    proof={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
           'job_id':args.job,'attempt':args.attempt_number,'recording_id':args.recording_id,
           'source_result_sha256':sha(result_path),'frames':600,'video_sha256':sha(video),
           'trace_sha256':sources['trace.jsonl'],'checks':{name:True for name in CHECKS},
           'auditor_path':str(Path(__file__).resolve()),'auditor_sha256':sha(Path(__file__).resolve()),
           'source_decode_receipt_path':str(decode),'source_decode_receipt_sha256':sha(decode),
           'source_decode_auditor_sha256':verified['auditor_sha256'],
           'source_sha256':sources,'physical_or_legal_acceptance_claimed':False}
    output.write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def selftest(case,negative):
    sample={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
            'setup_confirmed':True,'maneuver_completed':True,'accepted':False,
            'measured_values':{'frames':[{}]*600,'stationary_sample_count':100},
            'recording_evidence':[{'name':name} for name in (
                'ego_pose','stop_distance_on_signal_approach','kin.speed','dev.traffic_signal',
                'dev.position','rel.centre_distance','drv.approaching','rel.occupies',
                'drv.standing_or_parked','drv.forced_halt','dev.human_direction')]}
    if negative:
        sample['provenance_kind']='synthetic_fixture'
        check_result(sample,case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample,case)
    for key,value in (('maneuver_completed',False),('measured_values',{}),('recording_evidence',[])):
        changed=dict(sample); changed[key]=value
        try:check_result(changed,case)
        except ValueError:pass
        else:raise AssertionError('Missing original evidence accepted: '+key)
    return {'case_id':case,'source_predicates_tested':True,'original_capture_attested':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--negative',action='store_true')
    parser.add_argument('--attempt');parser.add_argument('--operations');parser.add_argument('--output')
    parser.add_argument('--video',default='primary.mkv')
    parser.add_argument('--review',default='context-survey.json')
    parser.add_argument('--job',type=int);parser.add_argument('--attempt-number',type=int)
    parser.add_argument('--recording-id')
    args=parser.parse_args()
    print(json.dumps(selftest(args.case,args.negative) if args.self_test else audit(args)))
