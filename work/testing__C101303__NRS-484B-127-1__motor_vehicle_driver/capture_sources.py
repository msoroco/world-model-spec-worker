"""Write original frame-joined complete bodies, velocities and road state.

Caller supplies four sensor frames for this snapshot before invoking record_sample.
No controller target is written as a measured speed or body gap.
"""
import json
import math

def _vertices(actor):
    transform=actor.get_transform()
    values=actor.bounding_box.get_world_vertices(transform)
    if len(values)<4:raise ValueError('Missing Native complete-body vertices')
    result=[[float(v.x),float(v.y)] for v in values]
    if not all(math.isfinite(v) for p in result for v in p):raise ValueError('Nonfinite Native body')
    return result

def _velocity(actor):
    value=actor.get_velocity()
    result=[float(value.x),float(value.y),float(value.z)]
    if not all(math.isfinite(v) for v in result):raise ValueError('Nonfinite Native velocity')
    return result

def _actor_row(actor,lane_id):
    return {'actor_id':actor.id,'lane_id':lane_id,'body_vertices_xy_m':_vertices(actor),
            'velocity_mps':_velocity(actor),'speed_source':'actor.get_velocity',
            'brake_applied':bool(actor.get_control().brake>0)}

def record_sample(frame_map,history_stream,trace_stream,evidence_stream,
                  snapshot,ego,lead,*,road_id,ego_lane_id,lead_lane_id,
                  surface_condition,traffic_actor_ids,lane_change_started):
    frame,time=snapshot.frame,snapshot.timestamp.elapsed_seconds
    if type(lane_change_started) is not bool:raise ValueError('Missing lane change state')
    ego_row=_actor_row(ego,ego_lane_id);lead_row=_actor_row(lead,lead_lane_id)
    history={'frame':frame,'time_s':time,'road_id':road_id,
             'ego':ego_row,'lead':lead_row,'surface_condition':surface_condition,
             'traffic_actor_ids':list(traffic_actor_ids),'lane_change_started':lane_change_started}
    ego_location=ego.get_location();ego_velocity=ego_row['velocity_mps']
    trace={'frame':frame,'time_s':time,'position_m':[ego_location.x,ego_location.y,ego_location.z],
           'velocity_mps':ego_velocity,'speed_mps':math.sqrt(sum(v*v for v in ego_velocity)),
           'heading_deg':ego.get_transform().rotation.yaw}
    evidence={'frame':frame,'time_s':time,'ego_actor_id':ego.id,'lead_actor_id':lead.id,
              'sensor_frames_joined':True,'source_camera_names':['overview','approach','reference_corner','driver_reference']}
    mapping=frame_map.append(frame,time)
    for stream,row in ((history_stream,history),(trace_stream,trace),(evidence_stream,evidence)):
        stream.write(json.dumps(row,allow_nan=False)+'\n')
    return {'video_frame':mapping['video_frame'],'history':history,'trace':trace,'evidence':evidence}
