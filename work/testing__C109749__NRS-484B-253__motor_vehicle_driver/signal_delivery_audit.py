"""Independent C109749 original-source delivery audit.

The local operator copies this script into state/operations/worker_exchange.
Diagnostic joins test software only; a live audit requires a sealed Native attempt,
full planned duration, independent pixel review, physical checks, and full decode.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = next((p for p in Path(__file__).resolve().parents if (p/'runtime/scenario_pipeline').is_dir()), None)
if REPO is None:
    raise RuntimeError('Pinned runtime unavailable')
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange import media
from worker_exchange.capture import PROFILE

CAMERAS = ('overview','approach','reference_corner','driver_reference')
ROLES = ('ego','oncoming','reciprocal')
CHECKS = ('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')
SIGNAL_BRANCHES = {
    'testing__C109749__NRS-484B-253__motor_vehicle_driver__signal_omitted': 'omitted',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: '+path.name)
    return json.loads(path.read_text())


def rows(path):
    path=Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: '+path.name)
    result=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError('Empty original source: '+path.name)
    return result


def validate_originals(root,case_id,*,full_duration=True):
    root=Path(root)
    config=read(root/'config.json')
    if config.get('selected_case_id')!=case_id or config.get('rate_hz')!=20:
        raise ValueError('Exact selected case or capture cadence differs')
    geometry=read(root/'intersection_geometry.json')
    polygon=geometry.get('intersection_polygon_xy_m')
    if not isinstance(polygon,list) or len(polygon)<3 or any(
            not isinstance(v,list) or len(v)!=2 or any(not math.isfinite(float(x)) for x in v)
            for v in polygon):
        raise ValueError('Original junction geometry incomplete')
    mapping=rows(root/'video_frames.jsonl')
    history=rows(root/'interaction_history.jsonl')
    trace=rows(root/'trace.jsonl')
    if len(mapping)!=len(history) or len(mapping)!=len(trace):
        raise ValueError('Original frame count differs among sources')
    if full_duration and len(mapping)!=config['rate_hz']*config['duration_s']:
        raise ValueError('Original sources do not cover full planned duration')
    ids=None
    prev_frame=prev_time=None
    for index,(frame,motion,source) in enumerate(zip(mapping,history,trace)):
        native=frame.get('carla_frame',frame.get('native_frame'))
        time=frame.get('time_s')
        if (frame.get('video_frame')!=index or type(native) is not int or
                type(time) not in (int,float) or not math.isfinite(time) or
                motion.get('frame')!=native or source.get('frame')!=native or
                abs(motion.get('time_s',math.inf)-time)>1e-3 or
                abs(source.get('time_s',math.inf)-time)>1e-3 or
                (prev_frame is not None and (native<=prev_frame or time<=prev_time))):
            raise ValueError('Original frame/time join differs')
        participants=[]
        for role in ROLES:
            actor=motion.get(role)
            if not isinstance(actor,dict) or type(actor.get('actor_id')) is not int:
                raise ValueError('Missing complete participant: '+role)
            vertices=actor.get('body_vertices_xy_m')
            velocity=actor.get('velocity_xy_mps')
            if (not isinstance(vertices,list) or len(vertices)<4 or
                    any(not isinstance(v,list) or len(v)!=2 or any(not math.isfinite(float(x)) for x in v) for v in vertices) or
                    not isinstance(velocity,list) or len(velocity)!=2 or
                    any(not math.isfinite(float(x)) for x in velocity)):
                raise ValueError('Missing complete participant body: '+role)
            participants.append(actor['actor_id'])
        if len(set(participants))!=len(ROLES):
            raise ValueError('Three distinct participant identities required')
        if ids is None:
            ids=participants
        elif participants!=ids:
            raise ValueError('Participant identities changed during capture')
        heading=motion.get('ego_heading_deg')
        if type(heading) not in (int,float) or not math.isfinite(heading) or type(motion.get('ego_left_indicator')) is not bool:
            raise ValueError('Original turn or indicator readback missing')
        prev_frame,prev_time=native,time
    return {'frames':len(mapping),'participant_ids':ids,
            'frame_map_sha256':sha(root/'video_frames.jsonl'),
            'history_sha256':sha(root/'interaction_history.jsonl'),
            'trace_sha256':sha(root/'trace.jsonl'),
            'geometry_sha256':sha(root/'intersection_geometry.json')}


def review_checker(samples,width,height):
    pending={}
    for row in samples:
        pending.setdefault(row['video_frame'],[]).append(row)
    if not pending:
        raise ValueError('Independent pixel review has no samples')
    seen=set()
    def check(frame):
        if frame.width!=width or frame.height!=height:
            raise ValueError('Reviewed camera dimensions differ')
        for row in pending.get(frame.index,[]):
            box=row.get('bbox_xyxy')
            if not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box):
                raise ValueError('Reviewed actor pixel box missing')
            x0,y0,x1,y1=box
            if not (0<=x0<x1<=width and 0<=y0<y1<=height and (x1-x0)*(y1-y0)>=16):
                raise ValueError('Reviewed actor pixel box invalid')
            colors=set()
            for y in range(y0,y1):
                for x in range(x0,x1):
                    offset=3*(y*width+x)
                    colors.add(frame.pixels[offset:offset+3])
                    if len(colors)>2:break
                if len(colors)>2:break
            if len(colors)<2 or colors=={b'\x00\x00\x00'}:
                raise ValueError('Reviewed actor ROI has no visible pixel detail')
            seen.add((frame.index,row['actor_id']))
    def finish():
        expected={(row['video_frame'],row['actor_id']) for row in samples}
        if seen!=expected:
            raise ValueError('Reviewed actor pixel frame was not decoded')
    return check,finish


def validate_signal_sequence(root,branch,result):
    """Independently recompute omitted signal and yield-before-turn from originals."""
    from shapely.geometry import MultiPoint, Polygon
    geometry=read(root/'intersection_geometry.json')
    polygon=Polygon(geometry['intersection_polygon_xy_m'])
    history=rows(root/'interaction_history.jsonl')
    if branch!='omitted' or not polygon.is_valid or polygon.is_empty:
        raise ValueError('Original signal branch or junction polygon invalid')
    body=lambda row,role: MultiPoint(row[role]['body_vertices_xy_m']).convex_hull
    if not polygon.covers(body(history[0],'oncoming')):
        raise ValueError('Initial opposing complete body is not inside original junction')
    if any(row['ego_left_indicator'] for row in history):
        raise ValueError('Original left indicator was not omitted')
    direction=geometry['oncoming_direction_xy'];conflict=geometry['conflict_point_xy_m']
    clearance=next((row['frame'] for row in history[1:]
                    if not polygon.intersects(body(row,'oncoming'))
                    and sum((conflict[i]-row['oncoming']['position_xy_m'][i])*direction[i]
                            for i in (0,1))<0),None)
    heading=history[0]['ego_heading_deg']
    turn=next((row['frame'] for row in history
               if abs((row['ego_heading_deg']-heading+180)%360-180)>=15),None)
    yielded=[row['frame'] for row in history if polygon.intersects(body(row,'ego'))
             and polygon.intersects(body(row,'oncoming'))
             and math.hypot(*row['ego']['velocity_xy_mps'])<0.1]
    if not yielded or clearance is None or turn is None or not max(yielded)<clearance<turn:
        raise ValueError('Original unsignalled yield and turn order missing')
    saved=result.get('measured_values',{})
    if (saved.get('subject_yield_frames')!=yielded or
            saved.get('ego_left_indicator_frames')!=[] or
            saved.get('initial_oncoming_clearance_frame')!=clearance or
            saved.get('ego_turn_start_frame')!=turn):
        raise ValueError('Saved signal measurement differs from original source')
    return {'branch':'omitted','subject_yield_frames':yielded,
            'ego_left_indicator_frames':[],'initial_oncoming_clearance_frame':clearance,
            'ego_turn_start_frame':turn,'legal_verdict_asserted':False}


def audit_attempt(attempt,case_id,job_id,attempt_number,recording_id,pixel_review,output,decode_receipt,
                  *,diagnostic_selftest=False):
    if case_id not in SIGNAL_BRANCHES:
        raise ValueError('Unsupported exact C109749 delivery case')
    root=Path(attempt).resolve();output=Path(output).resolve();decode_receipt=Path(decode_receipt).resolve()
    if output.name=='result.json' or root not in output.parents or root in decode_receipt.parents:
        raise ValueError('Audit output must remain under attempt; decode receipt must be external')
    result=read(root/'result.json')
    expected_kind='synthetic_fixture' if diagnostic_selftest else 'native'
    if (result.get('case_id')!=case_id or result.get('provenance_kind')!=expected_kind or
            result.get('diagnostic_fixture') is not diagnostic_selftest or result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Non-diagnostic Native result required')
    seal=read(root/'capture-seal.json')
    if (seal.get('format')!='worker-sealed-capture' or seal.get('provenance_kind')!=expected_kind or
            seal.get('diagnostic_fixture') is not diagnostic_selftest):
        raise ValueError('Non-diagnostic Native capture seal required')
    required={'config.json','interaction_history.jsonl','intersection_geometry.json','video_frames.jsonl','trace.jsonl',
              *(name+'.mkv' for name in CAMERAS)}
    if not required<=set(seal.get('sources',{})):
        raise ValueError('Capture seal omits required original source')
    for name,digest in seal['sources'].items():
        source=(root/name).resolve()
        if root not in source.parents or not source.is_file() or sha(source)!=digest:
            raise ValueError('Sealed original source changed: '+name)
    if read(root/'native-exit.json').get('capture_seal_sha256')!=sha(root/'capture-seal.json'):
        raise ValueError('Native exit does not bind capture seal')
    owner=read(root/'owner-release.json')
    if owner.get('operator_attested') is not True or owner.get('native_exit_sha256')!=sha(root/'native-exit.json'):
        raise ValueError('Owner release does not bind Native exit')
    joined=validate_originals(root,case_id)
    physical=result.get('physical_checks',{})
    if (physical.get('setup',{}).get('status')!='met' or
            physical.get('maneuver',{}).get('status')!='met' or
            not result.get('realized_observables')):
        raise ValueError('Source-bound physical completion absent')
    sequence=validate_signal_sequence(root,SIGNAL_BRANCHES[case_id],result)
    sources={name:root/(name+'.mkv') for name in CAMERAS}
    media.check_four_view_sources(sources)
    review=read(pixel_review)
    if (not review.get('reviewer') or not review.get('method') or review.get('case_id')!=case_id or
            review.get('frame_map_sha256')!=joined['frame_map_sha256'] or
            review.get('source_sha256')!={name:sha(path) for name,path in sources.items()}):
        raise ValueError('Independent pixel review missing or stale')
    observations=review.get('observations',[])
    if not observations or {x.get('actor') for x in observations}!=set(ROLES) or not all(
            any(x.get('camera')==name for x in observations) for name in CAMERAS):
        raise ValueError('Independent pixel review omits actor or camera')
    history=rows(root/'interaction_history.jsonl')
    for row in observations:
        i=row.get('video_frame')
        if type(i) is not int or not 0<=i<len(history) or row.get('actor') not in ROLES or row.get('camera') not in CAMERAS:
            raise ValueError('Pixel review refers to unknown frame, actor or camera')
        if row.get('actor_id')!=history[i][row['actor']]['actor_id']:
            raise ValueError('Pixel review actor identity differs from original source')
    sizes={'overview':PROFILE['overview'],**dict(zip(CAMERAS[1:],PROFILE['detail_views']))}
    for name,path in sources.items():
        sample=[x for x in observations if x['camera']==name]
        check,finish=review_checker(sample,*sizes[name])
        media.audit(path,joined['frames'],checkers={'reviewed_actor_pixels':(sha(__file__),check)},mapping_sha256=joined['frame_map_sha256'])
        finish()
    video=root/'raw.mkv'
    decoded=media.audit(video,joined['frames'],mapping_sha256=joined['frame_map_sha256'],receipt=decode_receipt)
    trace=root/'converted/trace.json'
    scenes=read(trace)['scenes']
    mapping=rows(root/'video_frames.jsonl')
    if len(scenes)!=joined['frames'] or any(s['t']!=round(f['time_s']*1000) for s,f in zip(scenes,mapping)):
        raise ValueError('Core trace/original frame time join differs')
    audit={'format':'worker-delivery-audit-diagnostic' if diagnostic_selftest else 'worker-delivery-audit',
           'passed':not diagnostic_selftest,'software_checks_passed':True,
           'diagnostic_fixture':diagnostic_selftest,'physical_acceptance_claimed':False,
           'case_id':case_id,'job_id':job_id,'attempt':attempt_number,'recording_id':recording_id,
           'checks':{key:True for key in CHECKS},'frames':joined['frames'],
           'source_result_sha256':sha(root/'result.json'),'video':'raw.mkv','video_sha256':sha(video),
           'trace':'converted/trace.json','trace_sha256':sha(trace),'original_sources':joined,'signal_sequence':sequence,
           'auditor_path':str(Path(__file__).resolve()),'auditor_sha256':sha(__file__),
           'source_decode_receipt_path':str(decode_receipt),'source_decode_receipt_sha256':sha(decode_receipt),
           'source_decode_auditor_sha256':decoded['auditor_sha256'],'pixel_review_sha256':sha(pixel_review)}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(audit,indent=2)+'\n')
    return audit


def main():
    p=argparse.ArgumentParser()
    for name in ('case','attempt','job-id','recording-id','pixel-review','output','decode-receipt'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--attempt-number',type=int,required=True)
    p.add_argument('--diagnostic-selftest',action='store_true')
    a=p.parse_args()
    print(json.dumps(audit_attempt(a.attempt,a.case,a.job_id,a.attempt_number,a.recording_id,
                                  a.pixel_review,a.output,a.decode_receipt,
                                  diagnostic_selftest=a.diagnostic_selftest),sort_keys=True))


if __name__=='__main__':main()
