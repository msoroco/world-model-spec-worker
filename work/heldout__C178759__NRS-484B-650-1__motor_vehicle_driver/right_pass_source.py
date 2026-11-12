"""Derive unreviewed two-pass candidates from retained original source rows."""

from math import isfinite

REQUESTS = ('first_right_pass_request', 'second_right_pass_request')


def candidates(rows, frame_map):
    if not isinstance(rows, list) or not isinstance(frame_map, list) or len(rows) != len(frame_map) or len(rows) < 6:
        raise ValueError('Original pass source/frame map coverage differs')
    ego_ids = {row.get('ego_actor_id') for row in rows}
    target_ids = {row.get('fixed_overtaken_actor_id') for row in rows}
    if len(ego_ids) != 1 or None in ego_ids or len(target_ids) != 1 or None in target_ids:
        raise ValueError('Fixed ego or overtaken vehicle identity differs')
    previous = None
    for row, video in zip(rows, frame_map):
        frame = row.get('frame')
        time_s = row.get('time_s')
        if frame != video.get('carla_frame') or time_s != video.get('time_s'):
            raise ValueError('Original pass/video frame join differs')
        if type(frame) is not int or not isinstance(time_s, (int, float)) or not isfinite(time_s):
            raise ValueError('Original pass frame/time missing')
        if previous is not None and (frame != previous[0] + 1 or time_s <= previous[1]):
            raise ValueError('Original pass source is discontinuous')
        previous = (frame, time_s)
        for key in ('ego_station_m', 'lead_station_m', 'right_of_mapped_road_edge_m'):
            value = row.get(key)
            if not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError('Original pass geometry missing: '+key)
        if not isinstance(row.get('mapped_driving_edge_xy_m'), list) or not isinstance(row.get('mapped_road_edge_xy_m'), list):
            raise ValueError('Driving and mapped road edges must be separate sources')
    episodes = []
    for name in REQUESTS:
        selected = [row for row in rows if row.get('requested_phase') == name]
        if len(selected) < 2:
            return {'status':'unverified','reason':'Missing original phase: '+name,
                    'episodes':episodes,'fixed_overtaken_actor_id':next(iter(target_ids))}
        first, last = selected[0], selected[-1]
        before = first['ego_station_m'] - first['lead_station_m']
        after = last['ego_station_m'] - last['lead_station_m']
        beyond = [row['frame'] for row in selected if row['right_of_mapped_road_edge_m'] > 0]
        if before >= -5 or after <= 5 or not beyond:
            return {'status':'unverified','reason':'Original order reversal or mapped-edge crossing absent: '+name,
                    'episodes':episodes,'fixed_overtaken_actor_id':next(iter(target_ids))}
        episodes.append({'start_frame':first['frame'],'end_frame':last['frame'],
                         'target_vehicle_id':next(iter(target_ids)),
                         'before_gap_m':before,'after_gap_m':after,
                         'rightward_separation_m':max(row['right_of_mapped_road_edge_m'] for row in selected),
                         'off_pavement_frames':beyond,
                         'surface_status':'unreviewed; mapped edge is not a pavement verdict'})
    first_end, second_start = episodes[0]['end_frame'], episodes[1]['start_frame']
    middle = [row for row in rows if first_end < row['frame'] < second_start]
    if not middle or not any(row['right_of_mapped_road_edge_m'] <= 0 for row in middle):
        return {'status':'unverified','reason':'No original mapped-edge reentry between requests',
                'episodes':episodes,'fixed_overtaken_actor_id':next(iter(target_ids))}
    if not any(row['ego_station_m'] - row['lead_station_m'] < -5 for row in middle):
        return {'status':'unverified','reason':'Fixed vehicle did not reclaim the lead',
                'episodes':episodes,'fixed_overtaken_actor_id':next(iter(target_ids))}
    return {'status':'candidate','episodes':episodes,
            'fixed_overtaken_actor_id':next(iter(target_ids)),
            'passing_violation_decided':False,'pavement_surface_decided':False,
            'immediate_hazard_decided':False,'aggressive_driving_decided':False}
