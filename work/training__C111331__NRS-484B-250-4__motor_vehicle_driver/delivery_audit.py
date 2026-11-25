"""Independent original-source delivery audit for NRS 484B.250(4).

Install this file as delivery_audit.py in local worker_exchange operations before
use. Self-tests exercise predicates only; no local fixture is accepted footage.
"""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('native_source','all_participants','time_join','full_video_decode',
          'actual_pixels','physical_completion')
BASE = 'training__C111331__NRS-484B-250-4__motor_vehicle_driver'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inside(root, name):
    path=(root/name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError('Missing original source: '+name)
    return path


def check_result(result, case):
    if result.get('case_id')!=case or result.get('provenance_kind')!='native' or result.get('diagnostic_fixture') is True:
        raise ValueError('Missing original source: exact original Native result')
    metric=result.get('measured_values',{})
    if metric.get('frames')!=600 or metric.get('legal_verdict') is not None or metric.get('actual_pixels_reviewed') is not False:
        raise ValueError('Unreliable original measurement or premature legal/pixel claim')
    if not all(metric.get('source_sha256',{}).get(x) for x in (
            'native-raw-actors.jsonl','native-signal-readback.jsonl',
            'native-map-readback.json','video_frames.jsonl')):
        raise ValueError('Missing source-bound original measurement')
    if not isinstance(metric.get('ego_entry_frame'),int) or not isinstance(metric.get('other_entry_frame'),int):
        raise ValueError('Physical junction entry incomplete')
    observed=bool(metric.get('pre_line_low_speed_frames'))
    if observed != case.endswith('controlled_1'):
        raise ValueError('Physical marked-line stop contrast incomplete')
    return metric


def check_review(review,case,video,mapping,metric):
    if (review.get('format')!='c111331-original-pixel-review-v1' or
            review.get('source_kind')!='original_native_review' or
            review.get('case_id')!=case or not review.get('reviewer_id') or
            review.get('video_sha256')!=sha(video) or
            review.get('video_frames_sha256')!=sha(mapping)):
        raise ValueError('Missing source-bound original pixel review')
    findings=review.get('findings',{})
    for key in ('ego_visible','other_visible','both_heads_uncovered',
                'both_heads_dark','marked_lines_visible','near_side_crosswalks_visible'):
        if findings.get(key) is not True:
            raise ValueError('Original pixel finding missing: '+key)
    frames=review.get('decisive_frames',{})
    for key in ('ego_entry','other_entry','governing_reference'):
        if not isinstance(frames.get(key),int) or not 0<=frames[key]<600:
            raise ValueError('Original decisive frame review incomplete: '+key)
    if frames['ego_entry']!=metric['ego_entry_frame'] or frames['other_entry']!=metric['other_entry_frame']:
        raise ValueError('Pixel review and original body entry differ')


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt=Path(args.attempt).resolve();output=Path(args.output).resolve();operations=Path(args.operations).resolve()
    if operations not in Path(__file__).resolve().parents or Path(__file__).name!='delivery_audit.py':
        raise ValueError('Independent auditor must run from local operations')
    if operations not in output.parents:
        raise ValueError('Audit output must stay in local operations')
    result_path=inside(attempt,'result.json');result=read(result_path)
    metric=check_result(result,args.case)
    for name,digest in metric['source_sha256'].items():
        if sha(inside(attempt,name))!=digest:
            raise ValueError('Original measurement source hash differs: '+name)
    seal=read(inside(attempt,'capture-seal.json'))
    if seal.get('format')!='worker-sealed-capture' or seal.get('diagnostic_fixture') is True or seal.get('frames')!=600:
        raise ValueError('Missing sealed original Native acquisition')
    mapping=inside(attempt,'video_frames.jsonl')
    rows=[json.loads(x) for x in mapping.read_text().splitlines()]
    if len(rows)!=600 or any(row.get('video_frame')!=i for i,row in enumerate(rows)):
        raise ValueError('Original frame map incomplete')
    trace=inside(attempt,args.trace);video=inside(attempt,args.video)
    scenes=read(trace).get('scenes',[])
    if len(scenes)!=600 or any(scene.get('t')!=round(row['time_s']*1000) for scene,row in zip(scenes,rows)):
        raise ValueError('Original Core/frame time join differs')
    review_path=inside(attempt,args.review)
    check_review(read(review_path),args.case,video,mapping,metric)
    decode=output.with_name('source-decode-'+args.case.rsplit('__',1)[-1]+'.json')
    media.audit(video,600,mapping_sha256=sha(mapping),receipt=decode)
    verified=media.verify_receipt(video,decode,600,mapping_sha256=sha(mapping))
    output.parent.mkdir(parents=True,exist_ok=True)
    payload={'format':'worker-delivery-audit','passed':True,'case_id':args.case,
        'job_id':args.job,'attempt':args.attempt_number,'recording_id':args.recording_id,
        'source_result_sha256':sha(result_path),'frames':600,
        'video':args.video,'video_sha256':sha(video),'trace':args.trace,
        'trace_sha256':sha(trace),'checks':{key:True for key in CHECKS},
        'auditor_path':str(Path(__file__).resolve()),'auditor_sha256':sha(Path(__file__).resolve()),
        'source_decode_receipt_path':str(decode),'source_decode_receipt_sha256':sha(decode),
        'source_decode_auditor_sha256':verified['auditor_sha256'],
        'human_review_sha256':sha(review_path),'physical_acceptance_claimed_by_fixture':False}
    output.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    return payload


def selftest(case,negative):
    sample={'case_id':case,'provenance_kind':'native','diagnostic_fixture':False,
        'measured_values':{'frames':600,'legal_verdict':None,'actual_pixels_reviewed':False,
        'source_sha256':{x:'0'*64 for x in ('native-raw-actors.jsonl','native-signal-readback.jsonl','native-map-readback.json','video_frames.jsonl')},
        'ego_entry_frame':300,'other_entry_frame':250,
        'pre_line_low_speed_frames':[180] if case.endswith('controlled_1') else []}}
    if negative:
        sample['provenance_kind']='synthetic_fixture'
        check_result(sample,case)
        raise AssertionError('Synthetic source accepted')
    check_result(sample,case)
    for bad in ('native-raw-actors.jsonl','native-signal-readback.jsonl'):
        changed=json.loads(json.dumps(sample));changed['measured_values']['source_sha256'].pop(bad)
        try:check_result(changed,case)
        except ValueError:pass
        else:raise AssertionError('Missing original source hash accepted: '+bad)
    return {'case_id':case,'source_predicates_tested':True,'original_capture_attested':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--self-test',action='store_true');p.add_argument('--negative',action='store_true')
    p.add_argument('--attempt');p.add_argument('--operations');p.add_argument('--output');p.add_argument('--trace',default='converted/trace.json');p.add_argument('--video',default='primary.mkv');p.add_argument('--review',default='human-review.json');p.add_argument('--job',type=int);p.add_argument('--attempt-number',type=int);p.add_argument('--recording-id')
    a=p.parse_args();print(json.dumps(selftest(a.case,a.negative) if a.self_test else audit(a),indent=2))
