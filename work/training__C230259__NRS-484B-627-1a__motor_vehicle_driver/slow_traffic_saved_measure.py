"""Original-source diagnostics for NRS 484B.627(1)(a), without a legal cutoff."""
import hashlib
import json
import math

ASSIGNMENT='training__C230259__NRS-484B-627-1a__motor_vehicle_driver'
CAMERAS={'overview','approach','reference_corner','driver_reference'}


def require(condition,message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def measure_original(raw_trace,raw_map,raw_context,raw_opendrive):
    trace=[json.loads(line) for line in raw_trace.splitlines() if line.strip()]
    frames=[json.loads(line) for line in raw_map.splitlines() if line.strip()]
    context=json.loads(raw_context)
    require(context.get('assignment_id')==ASSIGNMENT,'assignment source mismatch')
    require(context.get('map_source_sha256')==digest(raw_opendrive),'OpenDRIVE source hash mismatch')
    require(len(trace)==len(frames)==600,'original 600-frame source missing')
    survey=context.get('native_survey',{}).get('lanes',[])
    require([(x.get('name'),x.get('lane_id')) for x in survey]==[
        ('forward',-1),('opposing',1),('right_paved_margin',-2)],
        'one-lane-each-way Native survey missing')
    require(context.get('forward_lane_id')==-1 and context.get('opposing_lane_id')==1 and
            context.get('right_shoulder_lane_id')==-2 and
            context.get('right_paved_edge_y_m')==-6.5 and
            context.get('paved_width_m')==10.0,
            'paved width or right edge source missing')
    ego_id=trace[0].get('ego_id')
    follower_id=trace[0].get('traffic_id')
    require(ego_id and follower_id and ego_id!=follower_id,'separate participant identities missing')
    gaps=[]
    ego_speeds=[]
    follower_speeds=[]
    right_body_edges=[]
    follower_commands=[]
    previous=None
    for i,(row,frame) in enumerate(zip(trace,frames)):
        native=row.get('native_frame')
        require(type(native) is int and (previous is None or native>previous),
                'Native frame order missing')
        previous=native
        require(row.get('video_frame')==frame.get('video_frame')==i and
                frame.get('native_frame')==native and
                isinstance(row.get('time_s'),(int,float)) and
                abs(row['time_s']-i/20)<.005 and
                abs(frame.get('time_s',-999)-row['time_s'])<.005,
                'original trace/frame map join missing')
        cameras=row.get('camera_native_frames')
        require(cameras==frame.get('camera_native_frames') and
                isinstance(cameras,dict) and set(cameras)==CAMERAS and
                all(v==native for v in cameras.values()),
                'four-camera original frame join missing')
        require(row.get('ego_id')==ego_id and row.get('traffic_id')==follower_id,
                'participant identity changed')
        require(row.get('ego_road_id')=='1' and row.get('traffic_road_id')=='1' and
                row.get('ego_lane_id') in (-1,-2) and row.get('traffic_lane_id')==-1,
                'participant left sourced highway or expected lanes')
        ego=row.get('ego_xy_m')
        follower=row.get('traffic_xy_m')
        footprint=row.get('ego_footprint_xy_m')
        require(all(isinstance(p,list) and len(p)==2 and
                    all(isinstance(v,(int,float)) and math.isfinite(v) for v in p)
                    for p in (ego,follower)) and
                isinstance(footprint,list) and len(footprint)==4 and
                all(isinstance(p,list) and len(p)==2 and
                    all(isinstance(v,(int,float)) and math.isfinite(v) for v in p)
                    for p in footprint),
                'original participant pose or body source missing')
        if i<100:
            require(follower[0]<ego[0],'initial immediate follower longitudinal order missing')
        speed=row.get('ego_speed_mps')
        follower_speed=row.get('traffic_speed_mps')
        command=row.get('follower_command_mps')
        free=row.get('follower_free_flow_request_mps')
        require(all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in
                    (speed,follower_speed,command,free)) and free==5.0,
                'original speed or follower intent source missing')
        gaps.append(ego[0]-follower[0])
        ego_speeds.append(speed)
        follower_speeds.append(follower_speed)
        follower_commands.append(command)
        right_body_edges.append(min(p[1] for p in footprint))
    return {'format':'nrs-484b-627-1a-source-diagnostic-v1',
            'assignment_id':ASSIGNMENT,'frame_count':600,'duration_s':30,
            'trace_sha256':digest(raw_trace),'frame_map_sha256':digest(raw_map),
            'context_sha256':digest(raw_context),'opendrive_sha256':digest(raw_opendrive),
            'minimum_initial_follower_gap_m':min(gaps[:100]),
            'minimum_signed_longitudinal_gap_m':min(gaps),
            'maximum_follower_gap_m':max(gaps),
            'frames_follower_behind':sum(v>0 for v in gaps),
            'mean_subject_speed_mps':sum(ego_speeds)/600,
            'mean_follower_speed_mps':sum(follower_speeds)/600,
            'follower_command_below_free_flow_frames':sum(v<5 for v in follower_commands),
            'closest_right_body_edge_to_paved_edge_m':min(abs(v+6.5) for v in right_body_edges),
            'subject_right_body_edge_y_range_m':[min(right_body_edges),max(right_body_edges)],
            'one_lane_each_direction_surveyed':True,'paved_width_m':10.0,
            'highway_public_status_verified':bool(context.get('public_highway')),
            'nrs_484b_630_applicability':context.get('nrs_484b_630_applicability'),
            'impediment_legal_conclusion':None,'extreme_right_legal_conclusion':None,
            'physical_review_required':True}
