"""Saved-only original one-way lane, body and sign measurement."""

import json
from hashlib import sha256
from math import hypot
from pathlib import Path


def _rows(root,name):
    path=Path(root)/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_one_way(root):
    root=Path(root)
    roadway=_rows(root,'one_way_roadway.jsonl')
    signs=_rows(root,'one_way_sign.jsonl')
    frames=_rows(root,'video_frames.jsonl')
    trace=_rows(root,'trace.jsonl')
    if not roadway or not len(roadway)==len(signs)==len(frames)==len(trace):
        raise ValueError('One-way original source lengths differ')
    sign_id=None;ego_id=None;observations=[];initial_sign=None
    for index,(road,sign,frame,motion) in enumerate(zip(roadway,signs,frames,trace)):
        f,t=frame.get('carla_frame'),frame.get('time_s')
        if frame.get('video_frame')!=index or any(row.get('frame')!=f or row.get('time_s')!=t
                for row in (road,sign,motion)):
            raise ValueError('One-way original frame/time join differs')
        if index and (f!=frames[index-1]['carla_frame']+1 or
                      abs(t-frames[index-1]['time_s']-.05)>1e-4):
            raise ValueError('One-way source not continuous at 20 Hz')
        if sign.get('designation_verified') is not False or sign.get('posting_authority_verified') is not False:
            raise ValueError('One-way source claims unsupported authority')
        if 'oneway' not in sign.get('blueprint_id','').lower().replace('_',''):
            raise ValueError('One-way sign original type differs')
        if sign_id is None:sign_id=sign.get('actor_id')
        if ego_id is None:ego_id=road.get('ego_id')
        if not sign_id or not ego_id or sign.get('actor_id')!=sign_id or road.get('ego_id')!=ego_id:
            raise ValueError('One-way original actor identity changed')
        point=sign['position_m']
        if initial_sign is None:initial_sign=point
        if len(point)!=3 or sum((a-b)**2 for a,b in zip(point,initial_sign))>.01:
            raise ValueError('One-way sign moved from original placement')
        tangent=road['travel_tangent_xy'];left_tangent=road['left_lane_tangent_xy']
        if not .99<=hypot(*tangent)<=1.01 or not .99<=hypot(*left_tangent)<=1.01 or sum(
                tangent[i]*left_tangent[i] for i in (0,1))<.95:
            raise ValueError('One-way original lanes are not same-direction')
        right=(-tangent[1],tangent[0]);center=road['roadway_center_point_xy']
        def offset(point):return sum((point[i]-center[i])*right[i] for i in (0,1))
        left_edge=offset(road['left_road_edge_xy']);right_edge=offset(road['right_road_edge_xy'])
        corners=road['ego_corners']
        if not left_edge<0<right_edge or len(corners)!=4 or any(
                not left_edge<=offset(corner)<=right_edge for corner in corners):
            raise ValueError('One-way original road/body geometry invalid')
        if offset(point)<=right_edge:
            raise ValueError('One-way sign is not placed at right roadside')
        observations.append({'frame':f,'time_s':t,'minimum_body_right_offset_m':min(map(offset,corners)),
                             'roadway_width_m':right_edge-left_edge,
                             'sign_lateral_offset_m':offset(point)})
    return {'observations':observations,'sign_actor_id':sign_id,'subject_actor_id':ego_id,
            'minimum_body_right_offset_m':min(o['minimum_body_right_offset_m'] for o in observations),
            'designation_verified':False,'posting_authority_verified':False,
            'sources':{name:sha256((root/name).read_bytes()).hexdigest() for name in (
                'one_way_roadway.jsonl','one_way_sign.jsonl','video_frames.jsonl','trace.jsonl')}}
