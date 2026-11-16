"""Source-shaped full-body overtaking geometry and speed history; no legal finding."""
from math import hypot,isfinite


def _number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value)


def _body(record,name):
    body=record.get(name)
    if not isinstance(body,dict) or not body.get('id') or not _number(body.get('speed_mps')) or body['speed_mps']<0:
        raise ValueError('Missing original '+name+' identity or speed')
    corners=body.get('body_corners_xy_m')
    if not isinstance(corners,list) or len(corners)!=4 or any(not isinstance(p,list) or len(p)!=2 or not all(_number(x) for x in p) for p in corners):
        raise ValueError('Missing four original '+name+' body corners')
    if len({tuple(p) for p in corners})!=4:raise ValueError('Duplicate original body corners')
    return body,corners


def measure(frames,ego_id,overtaker_id):
    """Bracket complete passing from original body extents, retaining each 20 Hz sample.

    Each frame supplies original full-body corners and the source-surveyed local
    forward tangent. A positive rear-to-front gap means geometric completion at
    that sample only; the interval between frames remains unresolved.
    """
    if not ego_id or not overtaker_id or ego_id==overtaker_id:
        raise ValueError('Distinct overtaken and overtaking actor IDs required')
    if not isinstance(frames,list) or len(frames)<3:raise ValueError('Need original overtaking history')
    samples=[];previous=None
    for row in frames:
        frame,time=row.get('frame'),row.get('time_s')
        if type(frame) is not int or frame<0 or not _number(time):raise ValueError('Invalid original frame identity')
        if previous is not None and (frame<=previous[0] or abs(time-previous[1]-.05)>1e-6):
            raise ValueError('Original overtaking frames are unordered or not 20 Hz')
        previous=(frame,time)
        direction=row.get('road_forward_xy')
        if not isinstance(direction,list) or len(direction)!=2 or not all(_number(x) for x in direction):raise ValueError('Missing source-surveyed road forward tangent')
        length=hypot(*direction)
        if length<.9 or length>1.1:raise ValueError('Road tangent must be a near-unit original direction')
        forward=[x/length for x in direction];right=[forward[1],-forward[0]]
        ego,ec=_body(row,'ego');overtaker,oc=_body(row,'overtaker')
        if ego['id']!=ego_id or overtaker['id']!=overtaker_id:raise ValueError('Original actor identity changed')
        project=lambda corners,axis:[sum(p[i]*axis[i] for i in (0,1)) for p in corners]
        gap=min(project(oc,forward))-max(project(ec,forward))
        center=lambda corners:[sum(p[i] for p in corners)/4 for i in (0,1)]
        ecen,ocen=center(ec),center(oc)
        lateral=sum((ocen[i]-ecen[i])*right[i] for i in (0,1))
        ego_right=sum(ecen[i]*right[i] for i in (0,1))
        samples.append({'frame':frame,'time_s':time,'rear_to_front_gap_m':gap,
                        'full_body_passed_at_sample':gap>0,'overtaker_lateral_offset_right_m':lateral,
                        'ego_right_projection_m':ego_right,'ego_speed_mps':ego['speed_mps'],
                        'overtaker_speed_mps':overtaker['speed_mps']})
    first=next((i for i,x in enumerate(samples) if x['full_body_passed_at_sample']),None)
    if first==0:raise ValueError('Overtaker already completely ahead in first original frame')
    if first is not None and any(x['full_body_passed_at_sample'] for x in samples[:first]):raise ValueError('Inconsistent pass bracket')
    before=samples[:first] if first is not None else samples
    start=before[0]
    return {'samples':samples,'last_not_complete_frame':before[-1]['frame'],
            'first_complete_frame':samples[first]['frame'] if first is not None else None,
            'completion_interval_s':[before[-1]['time_s'],samples[first]['time_s']] if first is not None else None,
            'max_precompletion_speed_increase_mps':max(x['ego_speed_mps']-start['ego_speed_mps'] for x in before),
            'max_precompletion_step_speed_increase_mps':max((max(0.,b['ego_speed_mps']-a['ego_speed_mps']) for a,b in zip(before,before[1:])),default=0.),
            'post_completion_overlap_recurrence':any(not x['full_body_passed_at_sample'] for x in samples[first+1:]) if first is not None else None,
            'max_precompletion_right_shift_m':max(x['ego_right_projection_m']-start['ego_right_projection_m'] for x in before),
            'passing_side_at_first_frame':'right' if start['overtaker_lateral_offset_right_m']>0 else 'left' if start['overtaker_lateral_offset_right_m']<0 else 'aligned',
            'observation_or_hearing_confirmed':None,'right_pass_permission_confirmed':None,
            'physical_native_capture_confirmed':False,'legal_conclusion':None}
