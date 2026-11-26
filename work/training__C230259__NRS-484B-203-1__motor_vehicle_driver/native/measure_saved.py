"""Measure a sealed original meeting from separate source review, or CPU fixture."""
import hashlib
import json
from pathlib import Path
from meeting_math import measure as measure_rows

CAMERAS = ('overview','approach','reference_corner','driver_reference')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file(): raise ValueError('Missing required source: '+path.name)
    data=[json.loads(s) for s in path.read_text().splitlines()]
    if len(data)!=600:raise ValueError('Incomplete original source: '+path.name)
    return data


def reviewed_context(attempt,survey):
    kind=survey.get('source_kind')
    if kind=='synthetic_original_shape':
        if not survey.get('one_lane_each_direction_verified'):
            raise ValueError('Synthetic pavement context incomplete')
        return survey,None
    if kind!='original_native':raise ValueError('Original pavement survey missing')
    path=attempt/'source-review.json'
    if not path.is_file():raise ValueError('Original source review missing')
    review=json.loads(path.read_text())
    if review.get('format')!='worker-original-meeting-source-review' or review.get('case_id')!=json.loads((attempt/'config.json').read_text())['selected_case_id']:
        raise ValueError('Source review identity differs')
    required=['capture-seal.json','pavement-survey.json','native-motion.jsonl','video_frames.jsonl',*(name+'.mkv' for name in CAMERAS)]
    bound=review.get('source_sha256',{})
    if set(bound)!=set(required) or any(not (attempt/name).is_file() or sha(attempt/name)!=bound[name] for name in required):
        raise ValueError('Original source review binding differs')
    topics=review.get('confirmed_topics',{})
    for name in ('pavement_edges','opposite_directions','one_lane_each_direction','physical_constraints','body_footprints'):
        item=topics.get(name,{})
        if item.get('confirmed') is not True or not item.get('source_refs') or not set(item['source_refs'])<=set(required):
            raise ValueError('Original source review topic missing: '+name)
    data=dict(survey)
    for key in ('paved_left_y_m','paved_right_y_m','paved_center_y_m'):
        data[key]=review[key]
    data['one_lane_each_direction_verified']=True
    return data,sha(path)


def half_width(body):
    vertices=body.get('body_xyz_m')
    if not isinstance(vertices,list) or len(vertices)!=8 or any(not isinstance(v,list) or len(v)!=3 for v in vertices):
        raise ValueError('Original body vertices missing')
    ys=[v[1] for v in vertices]
    return max(ys)-min(ys)


def measure(attempt):
    attempt=Path(attempt)
    survey_path=attempt/'pavement-survey.json'
    if not survey_path.is_file():raise ValueError('Missing required source: pavement-survey.json')
    survey,review_sha=reviewed_context(attempt,json.loads(survey_path.read_text()))
    motion=rows(attempt/'native-motion.jsonl')
    frame_map=rows(attempt/'video_frames.jsonl')
    camera_sha={name:sha(attempt/(name+'.mkv')) for name in CAMERAS}
    converted=[]
    for i,(row,frame) in enumerate(zip(motion,frame_map)):
        native=row.get('native_frame')
        if row.get('video_frame')!=i or frame.get('video_frame')!=i or frame.get('native_frame')!=native or frame.get('camera_native_frames')!={name:native for name in CAMERAS} or abs(row.get('time_s',-1)-i/20)>1e-6 or abs(frame.get('time_s',-1)-i/20)>1e-6:
            raise ValueError('Original frame/camera join differs')
        ego=row.get('ego',{});other=row.get('oncoming',{})
        ep=ego.get('center_xyz_m');op=other.get('center_xyz_m')
        ev=ego.get('velocity_xyz_mps');ov=other.get('velocity_xyz_mps')
        if not all(isinstance(x,list) and len(x)==3 for x in (ep,op,ev,ov)):
            raise ValueError('Original two-body motion missing')
        converted.append({'video_frame':i,'native_frame':native,'time_s':row.get('time_s'),
            'source_cameras':{name:i for name in CAMERAS},
            'ego_x_m':ep[0],'oncoming_x_m':op[0],
            'ego_y_m':ep[1],'oncoming_y_m':op[1],
            'ego_width_m':half_width(ego),'oncoming_width_m':half_width(other),
            'ego_vx_mps':ev[0],'oncoming_vx_mps':ov[0]})
    context={'source_kind':'original_native_opposite_meeting_readback',
        'native_map_sha256':sha(attempt/'road.xodr'),
        'paved_bounds_sha256':sha(survey_path),
        'lane_direction_sha256':sha(survey_path),
        'ego_body_sha256':sha(attempt/'native-motion.jsonl'),
        'oncoming_body_sha256':sha(attempt/'native-motion.jsonl'),
        'vehicle_motion_sha256':sha(attempt/'native-motion.jsonl'),
        'one_lane_each_direction_verified':survey.get('one_lane_each_direction_verified'),
        'paved_left_y_m':survey.get('paved_left_y_m'),
        'paved_right_y_m':survey.get('paved_right_y_m'),
        'paved_center_y_m':survey.get('paved_center_y_m')}
    result=measure_rows(context,converted)
    result.update(source_kind=survey['source_kind'],source_review_sha256=review_sha,
        diagnostic_fixture=survey['source_kind']=='synthetic_original_shape',
        physical_acceptance_claimed=False,source_sha256={p.name:sha(p) for p in
            (survey_path,attempt/'native-motion.jsonl',attempt/'video_frames.jsonl')},
        camera_video_sha256=camera_sha)
    return result
