"""Join original parking sources; refuse unsourced authority and wheel units."""
import hashlib
import json
import math
from pathlib import Path
from measure_parking import CAMERAS,measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    if len(rows)!=600:raise ValueError('Incomplete saved source: '+path.name)
    return rows


def reviewed_context(attempt,context):
    if context.get('source_kind')=='synthetic_native_sample':
        return context,None
    if context.get('source_kind')!='original_native_parking_readback':
        raise ValueError('Original Native parking context missing')
    path=attempt/'source-review.json'
    if not path.is_file():raise ValueError('Original source review missing')
    review=json.loads(path.read_text())
    config=json.loads((attempt/'config.json').read_text())
    if review.get('format')!='worker-original-parking-source-review' or review.get('case_id')!=config['selected_case_id']:
        raise ValueError('Original review case identity differs')
    required={'capture-seal.json','road.xodr','parking-context.json','native-parking.jsonl',
              'video_frames.jsonl',*(name+'.mkv' for name in CAMERAS)}
    bound=review.get('source_sha256',{})
    if not required<=set(bound) or any(not (attempt/name).is_file() or sha(attempt/name)!=bound[name] for name in bound):
        raise ValueError('Original source review binding differs')
    topics=review.get('confirmed_topics',{})
    for name in ('adjacent_curbs','one_way_direction','wheel_layout_and_units',
                 'rest_interval','physical_parking','four_camera_visibility'):
        item=topics.get(name,{})
        if item.get('confirmed') is not True or not item.get('source_refs') or not set(item['source_refs'])<=set(bound):
            raise ValueError('Original source review missing topic: '+name)
    kind=context['parking_kind']
    admin=[]
    if kind=='left_ordinance':admin=['local_left_ordinance']
    elif kind in ('angle_ordinary','angle_dot'):admin=['local_angle_ordinance']
    if kind in ('angle_ordinary','angle_dot'):
        admin.append('dot_highway_designation')
    if kind=='angle_dot':admin.append('dot_width_determination')
    for name in admin:
        item=topics.get(name,{})
        if item.get('confirmed') is not True or not item.get('source_refs') or not set(item['source_refs'])<=set(bound):
            raise ValueError('Original administrative authority missing: '+name)
        metric_name={'local_left_ordinance':'left_ordinance',
                     'local_angle_ordinance':'angle_ordinance'}.get(name,name)
        context[metric_name+'_sha256']=sha(attempt/item['source_refs'][0])
    context=dict(context)
    context['highway_has_adjacent_curbs']=True
    context['one_way_highway']=True
    if kind in ('angle_ordinary','angle_dot'):
        if review.get('is_dot_maintained_highway') is not (kind=='angle_dot'):
            raise ValueError('Original DOT designation differs from exact case')
        context['dot_maintained_highway']=review['is_dot_maintained_highway']
    context['curb_geometry_sha256']=sha(attempt/'road.xodr')
    context['native_map_sha256']=sha(attempt/'road.xodr')
    context['wheel_geometry_sha256']=sha(attempt/'native-parking.jsonl')
    context['body_motion_sha256']=sha(attempt/'native-parking.jsonl')
    context['rest_state_sha256']=sha(attempt/'native-parking.jsonl')
    context['camera_manifest_sha256']=sha(attempt/'video_frames.jsonl')
    if 'local_left_ordinance' in admin:context['local_left_ordinance_status']='verified'
    if 'local_angle_ordinance' in admin:context['local_angle_ordinance_status']='verified'
    if 'dot_width_determination' in admin:context['dot_width_determination_status']='verified'
    return context,sha(path)


def native_wheel_edges(row,review):
    ego=row['ego']
    raw=ego.get('raw_wheel_geometry')
    layout=review.get('wheel_layout',{})
    scale=review.get('raw_wheel_units_per_m')
    half_width=review.get('wheel_half_width_m')
    if not isinstance(raw,list) or len(raw)<4 or not isinstance(scale,(int,float)) or scale<=0 or not isinstance(half_width,(int,float)) or half_width<=0:
        raise ValueError('Original wheel geometry conversion missing')
    pose=ego.get('center_xyz_m');yaw=ego.get('yaw_deg')
    if not isinstance(pose,list) or len(pose)!=3 or not isinstance(yaw,(int,float)):
        raise ValueError('Original body transform missing')
    sin=math.sin(math.radians(yaw));cos=math.cos(math.radians(yaw))
    values={}
    for side in ('right','left'):
        for axle in ('front','rear'):
            idx=layout.get(side+'_'+axle)
            if type(idx) is not int or idx<0 or idx>=len(raw):
                raise ValueError('Original wheel layout missing: '+side+'_'+axle)
            x,y,_=raw[idx]['position_raw_xyz']
            center_y=pose[1]+(x*sin+y*cos)/scale
            values[side+'_'+axle+'_wheel_outer_y_m']=center_y+half_width if side=='left' else center_y-half_width
    return values


def measure_attempt(attempt):
    attempt=Path(attempt)
    context_path=attempt/'parking-context.json'
    if not context_path.is_file():raise ValueError('Missing required source: parking-context.json')
    context,review_sha=reviewed_context(attempt,json.loads(context_path.read_text()))
    motion=read_rows(attempt/'native-parking.jsonl')
    frame_map=read_rows(attempt/'video_frames.jsonl')
    review=json.loads((attempt/'source-review.json').read_text()) if review_sha else None
    converted=[]
    for i,(row,frame) in enumerate(zip(motion,frame_map)):
        native=row.get('native_frame')
        if row.get('video_frame')!=i or frame.get('video_frame')!=i or frame.get('native_frame')!=native or frame.get('camera_native_frames')!={name:native for name in CAMERAS}:
            raise ValueError('Original frame/camera join differs')
        ego=row.get('ego',{})
        values=native_wheel_edges(row,review) if review is not None else {
            key:ego[key] for key in ('right_front_wheel_outer_y_m','right_rear_wheel_outer_y_m',
                                     'left_front_wheel_outer_y_m','left_rear_wheel_outer_y_m')}
        converted.append({'video_frame':i,'native_frame':native,'time_s':row.get('time_s'),
            'source_cameras':{name:i for name in CAMERAS},
            'ego_speed_mps':ego.get('speed_mps'),
            'stopped_or_parked':ego.get('stopped_or_parked') if review is None else
                ego.get('speed_mps',100)<=.1 and row.get('rest_mode_request') in ('stopped','parked'),
            'ego_heading_deg':ego.get('yaw_deg'),'curb_heading_deg':0,**values})
    metric=measure(context,converted)
    metric.update(source_review_sha256=review_sha,diagnostic_fixture=review_sha is None,
        physical_acceptance_claimed=False,source_sha256={name:sha(attempt/name) for name in
            ('parking-context.json','native-parking.jsonl','video_frames.jsonl')})
    return metric
