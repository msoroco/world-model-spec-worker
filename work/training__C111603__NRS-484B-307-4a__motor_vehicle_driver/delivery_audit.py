"""Independent original green-arrow, lawful-participant and pixel delivery gate."""

import argparse
import hashlib
import json
from pathlib import Path

VIEWS=('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(folder,name):
    path=(folder/name).resolve()
    if folder not in path.parents or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_result(result,case):
    if (result.get('case_id')!=case or result.get('provenance_kind')!='native'
            or result.get('diagnostic_fixture') is not False):
        raise ValueError('Missing original exact-case Native source')
    if result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
        raise ValueError('Original physical turn unverified')
    facts=result.get('measured_values',{})
    if (facts.get('frames')!=600 or facts.get('rate_hz')!=20
            or facts.get('first_ego_entry_frame') is None):
        raise ValueError('Original governed arrow and participant source unverified')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Original source prelabels legal outcome')
    return facts


def check_review(review,case,paths):
    if (review.get('format')!='worker-c111603-independent-source-review-v1'
            or review.get('case_id')!=case or not review.get('reviewer_id')):
        raise ValueError('Missing independent original governed-arrow source review')
    for name,path in paths.items():
        if review.get('source_sha256',{}).get(name)!=sha(path):
            raise ValueError('Independent review source changed: '+name)
    required=('governing_arrow_alone_pixels_reviewed','arrow_direction_and_duration_reviewed',
              'adjacent_crosswalk_lawfulness_reviewed','other_traffic_lawfulness_reviewed',
              'yield_causation_reviewed','actual_pixels_reviewed')
    if not all(review.get(name) is True for name in required):
        raise ValueError('Independent arrow, lawful-priority or yield source review absent')
    if (not review.get('source_documentation') or not review.get('reviewed_frames')
            or review.get('legal_verdict_claimed') is True):
        raise ValueError('Independent review lacks original source documentation')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    folder,output,operations=(Path(v).resolve() for v in
                              (args.attempt,args.output,args.operations))
    if operations not in output.parents or operations not in Path(__file__).resolve().parents:
        raise ValueError('Independent audit output must stay in operations')
    result=json.loads(source(folder,'result.json').read_text())
    check_result(result,args.case)
    names=('native.jsonl','signal_frames.jsonl','motion_frames.jsonl',
           'intersection-context.json','context-survey.json',
           'video_frames.jsonl','trace.jsonl')+tuple(view+'.mkv' for view in VIEWS)
    paths={name:source(folder,name) for name in names}
    review=json.loads(source(folder,args.review).read_text())
    check_review(review,args.case,paths)
    context=json.loads(paths['intersection-context.json'].read_text())
    survey=json.loads(paths['context-survey.json'].read_text())
    if (context.get('source_kind')!='original_native_context_survey'
            or survey.get('source_kind')!='original_native_context_survey'
            or survey.get('diagnostic_fixture') is True
            or not context.get('arrow_facing_source')
            or not context.get('arrow_only_pixels_source')):
        raise ValueError('Original governing-head survey absent')
    native,signal,motion,frames,trace=(rows(paths[name]) for name in
        ('native.jsonl','signal_frames.jsonl','motion_frames.jsonl','video_frames.jsonl','trace.jsonl'))
    if not all(len(item)==600 for item in (native,signal,motion,frames,trace)):
        raise ValueError('Original 600-frame arrow source join differs')
    for i,(n,s,m,f,t) in enumerate(zip(native,signal,motion,frames,trace)):
        if (f.get('video_frame')!=i or
                any(row.get('native_frame')!=f.get('native_frame') for row in (n,s,m))
                or t.get('frame')!=f.get('native_frame')
                or any(abs(row.get('time_s',-100)-f.get('time_s',100))>1e-4
                       for row in (n,s,m))):
            raise ValueError('Original arrow motion and pixels join differs')
    decoded={}
    for view in VIEWS:
        receipt=output.with_name(output.stem+'-'+view+'-decode.json')
        media.audit(paths[view+'.mkv'],600,
            mapping_sha256=sha(paths['video_frames.jsonl']),receipt=receipt)
        media.verify_receipt(paths[view+'.mkv'],receipt,600,
            mapping_sha256=sha(paths['video_frames.jsonl']))
        decoded[view]=sha(receipt)
    proof={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
        'checks':{name:True for name in ('native_source','all_participants',
            'time_join','full_video_decode','actual_pixels','physical_completion')},
        'source_result_sha256':sha(folder/'result.json'),
        'independent_review_sha256':sha(folder/args.review),
        'source_decode_receipts':decoded,'frames':600,'legal_verdict_claimed':False}
    output.write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def selftest(case,negative):
    result={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
        'accepted':False,'legal_verdict_claimed':False,
        'physical_checks':{'maneuver':{'status':'met'}},
        'measured_values':{'frames':600,'rate_hz':20,'first_ego_entry_frame':200}}
    if negative:
        result['measured_values']['first_ego_entry_frame']=None
        check_result(result,case)
        raise AssertionError('Missing original governed-arrow entry accepted')
    check_result(result,case)
    for key,value in (('provenance_kind','synthetic_fixture'),('accepted',True)):
        altered=json.loads(json.dumps(result));altered[key]=value
        try:check_result(altered,case)
        except ValueError:pass
        else:raise AssertionError('Invalid original-source predicate accepted: '+key)
    review={'format':'worker-c111603-independent-source-review-v1',
        'case_id':case,'reviewer_id':'independent_cpu_predicate_test',
        'source_sha256':{},'source_documentation':['fixture predicate only'],
        'reviewed_frames':[0,599],
        'governing_arrow_alone_pixels_reviewed':True,
        'arrow_direction_and_duration_reviewed':True,
        'adjacent_crosswalk_lawfulness_reviewed':True,
        'other_traffic_lawfulness_reviewed':True,
        'yield_causation_reviewed':True,'actual_pixels_reviewed':True,
        'legal_verdict_claimed':False}
    check_review(review,case,{})
    altered=dict(review,other_traffic_lawfulness_reviewed=False)
    try:check_review(altered,case,{})
    except ValueError:pass
    else:raise AssertionError('Missing lawful-traffic review accepted')
    return {'case_id':case,'predicates_tested':True,'original_capture_attested':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--negative',action='store_true')
    parser.add_argument('--attempt');parser.add_argument('--operations')
    parser.add_argument('--output');parser.add_argument('--review',default='independent-review.json')
    args=parser.parse_args()
    print(json.dumps(selftest(args.case,args.negative) if args.self_test else audit(args)))
