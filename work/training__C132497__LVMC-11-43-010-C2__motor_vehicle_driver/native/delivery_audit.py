"""Proposed independent original Native delivery audit for C132497.

Local operations must copy this file as delivery_audit.py before acceptance.
The CPU tests exercise its checks with synthetic data and claim no original capture.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ASSIGNMENT='training__C132497__LVMC-11-43-010-C2__motor_vehicle_driver'
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode',
        'actual_pixels','physical_completion')
CLAIMS={'vehicle','right_lane','exit_path','road_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):
    path=Path(path)
    require(path.is_file(),'Missing delivery source: '+str(path))
    return json.loads(path.read_text())


def lines(path):
    path=Path(path)
    require(path.is_file(),'Missing delivery source: '+str(path))
    return [json.loads(row) for row in path.read_text().splitlines() if row.strip()]


def validate_rows(raw,frames,trace,case,candidate,source_kind='original_native'):
    require(len(raw)==len(frames)==len(trace)==240,
            'Original actor/frame/trace count differs')
    start=raw[0].get('native_frame')
    require(type(start) is int,'Original Native frame identity absent')
    roads=[];circle=[];exits=[];previous_phase=-1
    for i,(row,frame,point) in enumerate(zip(raw,frames,trace)):
        t=row.get('time_s')
        require(row.get('source_kind')==source_kind and
                row.get('frame')==i and row.get('native_frame')==start+i and
                frame.get('video_frame')==i and frame.get('native_frame')==start+i and
                point.get('frame')==start+i and
                frame.get('carla_frame')==start+i and
                type(t) in (int,float) and math.isfinite(t) and
                abs(frame.get('time_s',-999)-t)<1e-6 and
                abs(point.get('time_s',-999)-t)<1e-6 and
                row.get('observed_road_id') in (20,21,22,23) and
                row.get('observed_lane_id') in (-2,-1),
                'Original actor/frame/trace join differs at '+str(i))
        ego=row.get('ego',{})
        require(ego.get('actor_id') is not None and
                isinstance(ego.get('center_native_xyz_m'),list) and
                len(ego['center_native_xyz_m'])==3 and
                all(type(v) in (int,float) and math.isfinite(v)
                    for v in ego['center_native_xyz_m']) and
                type(ego.get('speed_mps')) in (int,float) and
                math.isfinite(ego['speed_mps']) and ego['speed_mps']>=0,
                'Original ego pose or velocity missing at '+str(i))
        roads.append(row['observed_road_id'])
        phase={20:0,21:1,22:2}.get(row['observed_road_id'],-1)
        require(phase>=previous_phase and phase>=0,
                'Original first right-exit phases reverse or loop unexpectedly')
        previous_phase=phase
        if row['observed_road_id'] in (21,23):circle.append(row)
        if row['observed_road_id']==22:exits.append(row)
    require(roads[0]==20 and roads[-1]==22 and len(circle)>=10 and len(exits)>=5,
            'Original right-exit physical path incomplete')
    require(circle[-1]['observed_lane_id']==exits[0]['observed_lane_id'],
            'Original exit transition changes lane unexpectedly')
    expected=-2 if case.endswith('__reference') else -1
    require(circle[-1]['observed_lane_id']==expected,
            'Original exit lane differs from exact case')
    return {'frames':len(raw),'circulating_frames':len(circle),
            'exit_frames':len(exits),'exit_lane_id':expected,
            'native_frame_first':start,'native_frame_last':start+len(raw)-1}


def validate_review(review,case,candidate,attempt,primary):
    require(review.get('source_kind')=='original_native_review' and
            isinstance(review.get('reviewer_id'),str) and
            review['reviewer_id'].strip() and
            review.get('case_id')==case and review.get('candidate_id')==candidate and
            all(review.get(key) is True for key in
                ('counterclockwise_roundabout_verified','right_lane_identity_reviewed',
                 'actual_right_exit_reviewed','operator_and_jurisdiction_reviewed')) and
            review.get('legal_verdict') is None,
            'Independent original road/lane/right-exit review incomplete')
    sources=review.get('sources',{})
    paths={'native-raw-actors.jsonl':attempt/'native-raw-actors.jsonl',
           'native-map-readback.json':attempt/'native-map-readback.json',
           'video_frames.jsonl':attempt/'video_frames.jsonl',
           'controller-intention.json':attempt/'controller-intention.json',
           'raw.mkv':primary}
    paths.update({name+'.mkv':attempt/(name+'.mkv') for name in CAMERAS})
    for name,path in paths.items():
        require(path.is_file() and sources.get(name)==sha(path),
                'Independent original review source hash differs: '+name)
    boxes=review.get('pixel_boxes')
    require(isinstance(boxes,list) and {x.get('claim') for x in boxes}>=CLAIMS,
            'Independent visual review lacks required pixel claims')
    return boxes


def pixel_checker(boxes,frames=240):
    by_frame={};seen=set();identities=set()
    for item in boxes:
        i=item.get('frame');rect=item.get('rect_xywh')
        require(type(i) is int and 0<=i<frames and
                isinstance(rect,list) and len(rect)==4 and
                all(type(v) is int for v in rect) and
                rect[2]>=2 and rect[3]>=2,
                'Invalid reviewed pixel box')
        key=(i,tuple(rect))
        require(key not in identities,'Reviewed pixel claims reuse one box')
        identities.add(key)
        by_frame.setdefault(i,[]).append(item)
    def check(frame):
        for item in by_frame.get(frame.index,[]):
            x,y,w,h=item['rect_xywh']
            require(x>=0 and y>=0 and x+w<=frame.width and y+h<=frame.height,
                    'Reviewed pixel box exceeds decoded video')
            values=[]
            for row in range(y,y+h):
                offset=(row*frame.width+x)*3
                values.extend(frame.pixels[offset:offset+w*3])
            require(values and max(values)>min(values),
                    'Reviewed pixel box is flat')
            seen.add(item['claim'])
    return check,seen


def media_module():
    for parent in Path(__file__).resolve().parents:
        root=parent/'runtime/pipeline/scenario_pipeline'
        if root.is_dir():
            sys.path.insert(0,str(root))
            from worker_exchange import media
            return media
    raise ValueError('Pinned media auditor unavailable')


def audit(case,job_id,attempt_number,recording_id,attempt,review_path,
          primary,decode_receipt,output):
    attempt=Path(attempt).resolve();primary=Path(primary).resolve()
    output=Path(output).resolve();decode_receipt=Path(decode_receipt).resolve()
    require(case in (ASSIGNMENT+'__reference',ASSIGNMENT+'__contrast'),
            'Wrong exact delivery case')
    require(type(job_id) is int and job_id>0 and type(attempt_number) is int and
            attempt_number>0 and isinstance(recording_id,str) and recording_id and
            attempt.parent.name==recording_id and attempt in output.parents,
            'Canonical job, recording or attempt identity differs')
    require(not output.exists() and not decode_receipt.exists() and
            decode_receipt.parent!=attempt,
            'Use fresh independent audit and operations-owned decode receipt')
    require(attempt in primary.parents and primary.is_file(),
            'Promoted primary video escapes the exact attempt')
    config=read(attempt/'config.json');result=read(attempt/'result.json')
    intention=read(attempt/'controller-intention.json')
    map_readback=read(attempt/'native-map-readback.json')
    capture=read(attempt/'native-capture-report.json')
    review=read(review_path)
    candidate=config.get('candidate_id')
    require(result.get('provenance_kind')=='original_native_unreviewed',
            'Synthetic or unreviewed result cannot establish original Native delivery')
    require(config.get('case_id')==case and result.get('case_id')==case and
            result.get('accepted') is False and
            intention.get('case_id')==case and intention.get('candidate_id')==candidate and
            intention.get('source_kind')=='authored_controller_route_before_motion' and
            intention.get('turn_direction')=='right' and
            intention.get('intended_exit_road_id')==22 and
            config.get('controller_intention_sha256')==sha(attempt/'controller-intention.json') and
            map_readback.get('road_sha256')==config.get('road_sha256') and
            capture.get('case_id')==case and capture.get('candidate_id')==candidate and
            capture.get('error') is None and capture.get('observed_frames')==240,
            'Original case, intention, map or capture identity differs')
    raw=lines(attempt/'native-raw-actors.jsonl')
    frames=lines(attempt/'video_frames.jsonl')
    trace=lines(attempt/'trace.jsonl')
    physical=validate_rows(raw,frames,trace,case,candidate)
    core_path=attempt/'converted/trace.json'
    core=read(core_path).get('scenes')
    require(isinstance(core,list) and len(core)==240 and
            all(frame['video_frame']==i and
                type(scene.get('t')) is int and
                scene['t']==round(frame['time_s']*1000)
                for i,(frame,scene) in enumerate(zip(frames,core))),
            'Original Core trace/frame timestamp join differs')
    boxes=validate_review(review,case,candidate,attempt,primary)
    media=media_module()
    media.check_four_view_sources({name:attempt/(name+'.mkv') for name in CAMERAS})
    callback,seen=pixel_checker(boxes)
    decoded=media.audit(primary,240,checkers={'c132497_reviewed_pixels':
        (sha(Path(__file__)),callback)},
        mapping_sha256=sha(attempt/'video_frames.jsonl'),receipt=decode_receipt)
    require(CLAIMS<=seen,'Full decode omitted reviewed visible features')
    sources={name:sha(attempt/name) for name in
        ('config.json','result.json','native-raw-actors.jsonl','video_frames.jsonl',
         'trace.jsonl','controller-intention.json','native-map-readback.json',
         'native-capture-report.json')}
    sources['converted/trace.json']=sha(core_path)
    sources.update({name+'.mkv':sha(attempt/(name+'.mkv')) for name in CAMERAS})
    sources['raw.mkv']=sha(primary)
    receipt={'format':'worker-delivery-audit','passed':True,'case_id':case,
        'candidate_id':candidate,'job_id':job_id,'attempt':attempt_number,
        'recording_id':recording_id,'source_result_sha256':sources['result.json'],
        'frames':240,'video':primary.relative_to(attempt).as_posix(),
        'video_sha256':sources['raw.mkv'],
        'trace':'converted/trace.json','trace_sha256':sources['converted/trace.json'],
        'frame_map_sha256':sources['video_frames.jsonl'],
        'checks':{name:True for name in CHECKS},
        'sources':sources,'review_sha256':sha(review_path),
        'auditor_path':str(Path(__file__).resolve()),
        'auditor_sha256':sha(Path(__file__)),
        'source_decode_receipt_path':str(decode_receipt),
        'source_decode_receipt_sha256':sha(decode_receipt),
        'source_decode_auditor_sha256':decoded['auditor_sha256'],
        'physical_observations':physical,'original_native_observed':True,
        'legal_verdict':None}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for arg in ('case','recording-id','attempt','review','primary','decode-receipt','output'):
        parser.add_argument('--'+arg,required=True)
    parser.add_argument('--job-id',required=True,type=int)
    parser.add_argument('--attempt-number',required=True,type=int)
    a=parser.parse_args()
    print(json.dumps(audit(a.case,a.job_id,a.attempt_number,a.recording_id,
        a.attempt,a.review,a.primary,a.decode_receipt,a.output),sort_keys=True))
