"""Independent original rail-source delivery audit with CPU predicate tests."""
import argparse
import hashlib
import json
from pathlib import Path
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
def inside(root,relative):
    path=(root/relative).resolve()
    if root.resolve() not in path.parents or not path.is_file():raise ValueError('Missing original source: '+relative)
    return path
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]
def check_result(result,case):
    if result.get('case_id')!=case or result.get('provenance_kind')!='native' or result.get('diagnostic_fixture') is not False:
        raise ValueError('Missing original source: exact original Native result')
    if result.get('setup_confirmed') is not True or result.get('maneuver_completed') is not True:
        raise ValueError('Original rail approach or physical completion incomplete')
    measured=result.get('measured_values',{})
    if (measured.get('frame_count')!=600 or measured.get('original_native_observed') is not True
            or measured.get('event_nearest_footprint_gap_m') is None):
        raise ValueError('Missing original measured rail footprint')
    required={'rail_footprint'}|({'exception_context'} if any(case.endswith('__'+branch+'_'+str(i)) for branch in ('traffic_conflict','other_law','police_direction','official_device') for i in (1,2)) else set())
    if not required<={item.get('name') for item in result.get('recording_evidence',[])}:
        raise ValueError('Missing original rail or context evidence channel')
    if result.get('legal_verdict_claimed') is True or result.get('physical_acceptance_claimed') is True:
        raise ValueError('Source finalizer preaccepted rail outcome')
def check_review(review,case,sources):
    if review.get('format')!='c229398-rail-original-review-v1' or review.get('case_id')!=case or not review.get('reviewer_id'):
        raise ValueError('Missing independent original rail review')
    if any(review.get(name+'_sha256')!=sha(path) for name,path in sources.items()):
        raise ValueError('Original review source changed')
    for name in ('both_physical_rails_reviewed','vehicle_body_footprint_reviewed','activity_reviewed','actual_pixels_reviewed','exception_context_reviewed'):
        if review.get(name) is not True:raise ValueError('Original rail, activity, context or pixel review missing: '+name)
    frames=review.get('reviewed_frames',[])
    if not frames or any(type(x) is not int or x<0 or x>=600 for x in frames):
        raise ValueError('Decisive original frame review missing')
    if review.get('legal_verdict_claimed') is True:raise ValueError('Independent review cannot prelabel legal outcome')
def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt=Path(args.attempt).resolve();output=Path(args.output).resolve();operations=Path(args.operations).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError('Independent audit must run in local operations')
    result_path=inside(attempt,'result.json');result=json.loads(result_path.read_text());check_result(result,args.case)
    sources={'rail_survey':inside(attempt,'original-rail-survey.json'),
             'actor':inside(attempt,'original-native-rows.jsonl'),
             'video_frames':inside(attempt,'video_frames.jsonl'),
             'capture_seal':inside(attempt,'capture-seal.json')}
    if 'exception_context' in {item.get('name') for item in result['recording_evidence']}:
        sources['exception_context']=inside(attempt,'exception-context.json')
    check_review(json.loads(inside(attempt,args.review).read_text()),args.case,sources)
    for item in result['recording_evidence']:inside(attempt,item['reference'])
    actor=rows(sources['actor']);mapping=rows(sources['video_frames'])
    if len(actor)!=600 or len(mapping)!=600 or any(actor[i].get('native_frame')!=mapping[i].get('native_frame') for i in range(600)):
        raise ValueError('Original actor, camera and frame join differs')
    trace=inside(attempt,args.trace);video=inside(attempt,args.video)
    if len(trace.read_text().splitlines())!=600:raise ValueError('Original trace length differs')
    decode=output.with_name('source-decode-'+args.case.split('__')[-1]+'.json')
    media.audit(video,600,mapping_sha256=sha(sources['video_frames']),receipt=decode)
    verified=media.verify_receipt(video,decode,600,mapping_sha256=sha(sources['video_frames']))
    proof={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
           'job_id':args.job,'attempt':args.attempt_number,'recording_id':args.recording_id,
           'source_result_sha256':sha(result_path),'frames':600,'video_sha256':sha(video),
           'trace_sha256':sha(trace),'checks':{name:True for name in CHECKS},
           'auditor_sha256':sha(Path(__file__).resolve()),'source_decode_receipt_sha256':sha(decode),
           'source_decode_auditor_sha256':verified['auditor_sha256'],
           'human_review_sha256':sha(inside(attempt,args.review))}
    output.write_text(json.dumps(proof,indent=2)+'\n');return proof
def selftest(case,negative):
    sample={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
            'setup_confirmed':True,'maneuver_completed':True,'legal_verdict_claimed':False,
            'physical_acceptance_claimed':False,
            'measured_values':{'frame_count':600,'original_native_observed':True,'event_nearest_footprint_gap_m':12.5},
            'recording_evidence':[{'name':'rail_footprint'},{'name':'exception_context'}]}
    if negative:
        sample['provenance_kind']='synthetic_fixture';check_result(sample,case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample,case)
    for key,value in (('maneuver_completed',False),('measured_values',{}),('recording_evidence',[])):
        changed=json.loads(json.dumps(sample));changed[key]=value
        try:check_result(changed,case)
        except ValueError:pass
        else:raise AssertionError('Missing original source accepted: '+key)
    return {'case_id':case,'source_predicates_tested':True,'original_capture_attested':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--self-test',action='store_true');p.add_argument('--negative',action='store_true');p.add_argument('--attempt');p.add_argument('--operations');p.add_argument('--output');p.add_argument('--trace',default='trace.jsonl');p.add_argument('--video',default='overview.mkv');p.add_argument('--review',default='rail-review.json');p.add_argument('--job',type=int);p.add_argument('--attempt-number',type=int);p.add_argument('--recording-id')
    a=p.parse_args();print(json.dumps(selftest(a.case,a.negative) if a.self_test else audit(a)))
