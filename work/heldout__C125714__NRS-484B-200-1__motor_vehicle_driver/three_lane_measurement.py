"""Saved-only original three-lane topology and body occupancy measurement."""

import json
from hashlib import sha256
from math import hypot
from pathlib import Path


SOURCES=('three_lane_roadway.jsonl','video_frames.jsonl','trace.jsonl')


def _rows(root,name):
    path=Path(root)/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_three_lane(root):
    root=Path(root)
    road,frames,trace=(_rows(root,name) for name in SOURCES)
    if not road or not len(road)==len(frames)==len(trace):
        raise ValueError('Three-lane original source lengths differ')
    ego_id=None;observations=[]
    for index,(row,frame,motion) in enumerate(zip(road,frames,trace)):
        f,t=frame.get('carla_frame'),frame.get('time_s')
        if frame.get('video_frame')!=index or any(
                item.get('frame')!=f or item.get('time_s')!=t for item in (row,motion)):
            raise ValueError('Three-lane original frame/time join differs')
        if index and (f!=frames[index-1]['carla_frame']+1 or
                      abs(t-frames[index-1]['time_s']-.05)>1e-4):
            raise ValueError('Three-lane source not continuous at 20 Hz')
        if ego_id is None:ego_id=row.get('ego_id')
        if not ego_id or row.get('ego_id')!=ego_id:
            raise ValueError('Three-lane original subject identity changed')
        ids=(row['right_lane_id'],row['center_lane_id'],row['far_left_lane_id'])
        if len(set(ids))!=3 or row.get('applicable_lane_rule_verified') is not False:
            raise ValueError('Three-lane rule or topology claim unsupported')
        tangent=row['travel_tangent_xy'];center_tangent=row['center_lane_tangent_xy']
        left_tangent=row['far_left_lane_tangent_xy']
        if any(not .99<=hypot(*item)<=1.01 for item in (tangent,center_tangent,left_tangent)) or (
                sum(tangent[i]*center_tangent[i] for i in (0,1))<.95 or
                sum(tangent[i]*left_tangent[i] for i in (0,1))>-.95):
            raise ValueError('Three-lane original direction pattern differs')
        widths=row['lane_widths_m']
        if len(widths)!=3 or any(width<=0 for width in widths):
            raise ValueError('Three-lane original lane widths missing')
        right=(-tangent[1],tangent[0]);center=row['roadway_center_point_xy']
        def offset(point):return sum((point[i]-center[i])*right[i] for i in (0,1))
        left_edge=offset(row['left_road_edge_xy']);right_edge=offset(row['right_road_edge_xy'])
        corners=row['ego_corners']
        if (not left_edge<0<right_edge or abs(right_edge-left_edge-sum(widths))>.05 or
                len(corners)!=4 or any(not left_edge<=offset(p)<=right_edge for p in corners)):
            raise ValueError('Three-lane original road/body geometry invalid')
        observations.append({'frame':f,'time_s':t,'roadway_width_m':right_edge-left_edge,
                             'minimum_body_right_offset_m':min(map(offset,corners))})
    return {'observations':observations,'subject_actor_id':ego_id,
            'minimum_body_right_offset_m':min(x['minimum_body_right_offset_m'] for x in observations),
            'minimum_roadway_width_m':min(x['roadway_width_m'] for x in observations),
            'applicable_lane_rule_verified':False,
            'sources':{name:sha256((root/name).read_bytes()).hexdigest() for name in SOURCES}}
