"""Independent source-bound parking delivery audit; no fixture can satisfy it."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode',
        'actual_pixels','physical_completion')
SOURCES=('capture-seal.json','road.xodr','parking-context.json','native-parking.jsonl',
         'video_frames.jsonl',*(name+'.mkv' for name in CAMERAS))
TOPICS=('adjacent_curbs','one_way_direction','wheel_layout_and_units','rest_interval',
        'physical_parking','four_camera_visibility')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def inside(root,name):
    path=(root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def check_result(result,case):
    if result.get('case_id')!=case or result.get('provenance_kind')!='native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Exact original Native result missing')
    metric=result.get('measured_values',{})
    if metric.get('format')!='worker-source-parking-measurement' or metric.get('diagnostic_fixture') is not False or metric.get('original_native_observed') is not True:
        raise ValueError('Original parking measurement missing')
    if metric.get('frame_count')!=600 or metric.get('rest_frames',0)<1 or metric.get('legal_compliance')!='unassessed':
        raise ValueError('Rest interval missing or premature legal claim')
    if not metric.get('source_review_sha256') or set(metric.get('source_sha256',{}))!=set(SOURCES[2:5]):
        raise ValueError('Original source hashes incomplete')
    for name in ('front_wheel_gap_in_min','front_wheel_gap_in_max',
                 'rear_wheel_gap_in_min','rear_wheel_gap_in_max',
                 'maximum_heading_difference_deg'):
        if not isinstance(metric.get(name),(int,float)):
            raise ValueError('Original wheel/curb metric missing: '+name)
    if not result.get('maneuver_completed') or result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
        raise ValueError('Original physical parking completion unproven')
    return metric


def check_review(review,case,video,mapping,metric):
    if review.get('format')!='c229398-original-pixel-and-law-review-v1' or review.get('case_id')!=case or not review.get('reviewer_id') or review.get('source_kind')!='original_native_review':
        raise ValueError('Original pixel/source review missing')
    if review.get('video_sha256')!=sha(video) or review.get('video_frames_sha256')!=sha(mapping):
        raise ValueError('Original review video/frame binding differs')
    findings=review.get('findings',{})
    for key in ('ego_visible','both_curbs_visible','wheel_contact_visible',
                'one_way_direction_confirmed','rest_state_confirmed',
                'physical_parking_confirmed'):
        if findings.get(key) is not True:
            raise ValueError('Original pixel finding missing: '+key)
    kind=metric['parking_kind']
    if kind=='left_ordinance' and findings.get('left_ordinance_source_reviewed') is not True:
        raise ValueError('Left-curb ordinance review missing')
    if kind.startswith('angle') and findings.get('angle_ordinance_source_reviewed') is not True:
        raise ValueError('Angle ordinance review missing')
    if kind=='angle_dot' and findings.get('dot_width_determination_source_reviewed') is not True:
        raise ValueError('DOT width determination review missing')
    if review.get('decisive_frames',{}).get('first_rest')!=metric['first_rest_frame']:
        raise ValueError('Original decisive rest frame differs')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt,output=Path(args.attempt).resolve(),Path(args.output).resolve()
    if output.exists():raise ValueError('Retain prior independent audit')
    result_path=inside(attempt,'result.json')
    metric=check_result(read(result_path),args.case)
    for name,digest in metric['source_sha256'].items():
        if sha(inside(attempt,name))!=digest:raise ValueError('Original metric source hash differs: '+name)
    seal=read(inside(attempt,'capture-seal.json'))
    if seal.get('format')!='worker-sealed-capture' or seal.get('diagnostic_fixture') is True:
        raise ValueError('Sealed original Native acquisition missing')
    source_review_path=inside(attempt,'source-review.json')
    source_review=read(source_review_path)
    if sha(source_review_path)!=metric['source_review_sha256'] or source_review.get('case_id')!=args.case or source_review.get('format')!='worker-original-parking-source-review':
        raise ValueError('Original source review binding differs')
    bound=source_review.get('source_sha256',{})
    if not set(SOURCES)<=set(bound) or any(sha(inside(attempt,name))!=digest for name,digest in bound.items()):
        raise ValueError('Original source review inventory differs')
    topics=list(TOPICS)
    kind=metric['parking_kind']
    if kind=='left_ordinance':topics+=['local_left_ordinance']
    if kind.startswith('angle'):topics+=['local_angle_ordinance','dot_highway_designation']
    if kind=='angle_dot':topics+=['dot_width_determination']
    if any(source_review.get('confirmed_topics',{}).get(name,{}).get('confirmed') is not True for name in topics):
        raise ValueError('Original authority/geometry review incomplete')
    mapping=inside(attempt,'video_frames.jsonl')
    rows=[json.loads(line) for line in mapping.read_text().splitlines()]
    if len(rows)!=600 or any(row.get('video_frame')!=i or row.get('camera_native_frames')!={name:row.get('native_frame') for name in CAMERAS} for i,row in enumerate(rows)):
        raise ValueError('Original four-camera frame map incomplete')
    video,trace=inside(attempt,args.video),inside(attempt,args.trace)
    scenes=read(trace).get('scenes',[])
    if len(scenes)!=600 or any(scene.get('t')!=round(row['time_s']*1000) for scene,row in zip(scenes,rows)):
        raise ValueError('Original Core/frame join differs')
    review_path=inside(attempt,args.review)
    check_review(read(review_path),args.case,video,mapping,metric)
    decode=output.with_name('source-decode-'+args.case.rsplit('__',1)[-1]+'.json')
    media.audit(video,600,mapping_sha256=sha(mapping),receipt=decode)
    media.verify_receipt(video,decode,600,mapping_sha256=sha(mapping))
    value={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
           'job_id':args.job,'recording_id':args.recording_id,
           'source_result_sha256':sha(result_path),'video_sha256':sha(video),
           'trace_sha256':sha(trace),'human_review_sha256':sha(review_path),
           'checks':{key:True for key in CHECKS},'physical_or_legal_acceptance_claimed_by_fixture':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(value,indent=2)+'\n')
    return value


def selftest(case,negative):
    suffix=case.rsplit('__',1)[-1]
    kind='default_right' if suffix.startswith('right_') else ('left_ordinance' if suffix.startswith('left_') else suffix)
    metric={'format':'worker-source-parking-measurement','parking_kind':kind,
        'diagnostic_fixture':False,'original_native_observed':True,
        'frame_count':600,'rest_frames':360,'first_rest_frame':240,
        'legal_compliance':'unassessed','source_review_sha256':'0'*64,
        'source_sha256':{name:'0'*64 for name in SOURCES[2:5]},
        'front_wheel_gap_in_min':18,'front_wheel_gap_in_max':18,
        'rear_wheel_gap_in_min':18,'rear_wheel_gap_in_max':18,
        'maximum_heading_difference_deg':0}
    sample={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
            'measured_values':metric,'maneuver_completed':True,
            'physical_checks':{'maneuver':{'status':'met'}}}
    if negative:
        sample['provenance_kind']='synthetic_local_diagnostic'
        check_result(sample,case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample,case)
    for name in metric['source_sha256']:
        changed=json.loads(json.dumps(sample))
        changed['measured_values']['source_sha256'].pop(name)
        try:check_result(changed,case)
        except ValueError:pass
        else:raise AssertionError('Missing source accepted: '+name)
    review={'format':'c229398-original-pixel-and-law-review-v1','case_id':case,
            'reviewer_id':'cpu-predicate-test','source_kind':'original_native_review',
            'video_sha256':sha(Path(__file__)),'video_frames_sha256':sha(Path(__file__)),
            'findings':{name:True for name in ('ego_visible','both_curbs_visible','wheel_contact_visible',
                'one_way_direction_confirmed','rest_state_confirmed','physical_parking_confirmed',
                'left_ordinance_source_reviewed','angle_ordinance_source_reviewed',
                'dot_width_determination_source_reviewed')},
            'decisive_frames':{'first_rest':240}}
    check_review(review,case,Path(__file__),Path(__file__),metric)
    print(json.dumps({'case_id':case,'cpu_predicates_passed':True,
                      'original_acquisition_claimed':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--negative',action='store_true')
    for name in ('attempt','output','video','trace','review','job','recording-id'):
        parser.add_argument('--'+name)
    args=parser.parse_args()
    selftest(args.case,args.negative) if args.self_test else audit(args)
