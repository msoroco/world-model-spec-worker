"""Independent original-source separator audit; CPU tests reject missing provenance."""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS=('native_source','all_participants','time_join','full_video_decode',
    'actual_pixels','physical_completion')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root,name):
    path=(root/name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def check_result(result,case):
    if result.get('case_id')!=case or result.get('provenance_kind')!='native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Missing original source: exact original Native result')
    if result.get('behavior_attempted') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original separator target motion incomplete')
    observed=result.get('measured_values',{})
    if observed.get('frame_count')!=600 or observed.get('legal_verdict_claimed') is not False:
        raise ValueError('Missing original separator body and lane measurement')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Source finalizer preaccepted legal outcome')
    if len(result.get('recording_evidence',[]))!=9:
        raise ValueError('Missing original separator source channels')


def check_review(review,case,paths):
    if review.get('format')!='c245532-separator-original-review-v1' or review.get('case_id')!=case or not review.get('reviewer_id'):
        raise ValueError('Missing independent original separator review')
    for name,path in paths.items():
        if review.get(name+'_sha256')!=sha(path):
            raise ValueError('Original review source changed: '+name)
    if not all(review.get(name) is True for name in ('controlled_access_reviewed',
        'entrance_lane_function_reviewed','official_white_line_reviewed',
        'vehicle_body_reviewed','actual_pixels_reviewed')):
        raise ValueError('Original line, roadway or pixels unreviewed')
    frames=review.get('reviewed_frames',[])
    if not frames or any(type(i) is not int or i<0 or i>=600 for i in frames):
        raise ValueError('Decisive original pixel review missing')
    if review.get('legal_verdict_claimed') is True:
        raise ValueError('Original review cannot prelabel legal outcome')


def audit(args):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"runtime"/"scenario_pipeline"))
    from worker_exchange import media
    attempt=Path(args.attempt).resolve();operations=Path(args.operations).resolve()
    output=Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path=source(attempt,'result.json');result=json.loads(result_path.read_text())
    check_result(result,args.case)
    sources={'motion':source(attempt,'native-motion.jsonl'),
        'video_frames':source(attempt,'video_frames.jsonl'),
        'separator_context':source(attempt,'separator-context.json'),
        'road':source(attempt,'road.xodr')}
    check_review(json.loads(source(attempt,args.review).read_text()),args.case,sources)
    rows=[json.loads(line) for line in sources['motion'].read_text().splitlines()]
    frames=[json.loads(line) for line in sources['video_frames'].read_text().splitlines()]
    if len(rows)!=600 or len(frames)!=600 or any(rows[i]['native_frame']!=frames[i]['native_frame'] or
        rows[i]['video_frame']!=i or frames[i]['video_frame']!=i for i in range(600)):
        raise ValueError('Original separator source frame join differs')
    for entry in result['recording_evidence']:source(attempt,entry['reference'])
    trace=source(attempt,args.trace);video=source(attempt,args.video)
    decode=output.with_name('source-decode-'+args.case.rsplit('__',1)[-1]+'.json')
    media.audit(video,600,mapping_sha256=sha(sources['video_frames']),receipt=decode)
    verified=media.verify_receipt(video,decode,600,mapping_sha256=sha(sources['video_frames']))
    proof={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
        'job_id':args.job,'attempt':args.attempt_number,'recording_id':args.recording_id,
        'source_result_sha256':sha(result_path),'frames':600,'video_sha256':sha(video),
        'trace_sha256':sha(trace),'checks':{name:True for name in CHECKS},
        'auditor_sha256':sha(Path(__file__).resolve()),
        'source_decode_receipt_sha256':sha(decode),
        'source_decode_auditor_sha256':verified['auditor_sha256'],
        'human_review_sha256':sha(source(attempt,args.review))}
    output.write_text(json.dumps(proof,indent=2)+'\n');return proof


def selftest(case,negative):
    sample={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
        'behavior_attempted':True,'maneuver_completed':True,'accepted':False,
        'legal_verdict_claimed':False,'measured_values':{'frame_count':600,
            'legal_verdict_claimed':False},
        'recording_evidence':[{'name':str(i)} for i in range(9)]}
    if negative:
        sample['provenance_kind']='synthetic_fixture';check_result(sample,case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample,case)
    for key,value in (('maneuver_completed',False),('recording_evidence',[]),
        ('measured_values',{})):
        changed={**sample,key:value}
        try:check_result(changed,case)
        except ValueError:pass
        else:raise AssertionError('Missing original source accepted: '+key)
    return {'case_id':case,'source_predicates_tested':True,
        'original_capture_attested':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    p.add_argument('--self-test',action='store_true');p.add_argument('--negative',action='store_true')
    p.add_argument('--attempt');p.add_argument('--operations');p.add_argument('--output')
    p.add_argument('--trace',default='converted/trace.json');p.add_argument('--video',default='primary.mkv')
    p.add_argument('--review',default='separator-review.json');p.add_argument('--job',type=int)
    p.add_argument('--attempt-number',type=int);p.add_argument('--recording-id')
    a=p.parse_args();print(json.dumps(selftest(a.case,a.negative) if a.self_test else audit(a)))
