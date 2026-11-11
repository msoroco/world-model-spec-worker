"""Write original joined ego/lead bodies and velocities beside PipelineCapture.

PipelineCapture owns trace.jsonl, capture/evidence.jsonl and Native graphs. The
caller must join all four sensor frames for this world tick before this call.
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

def record_sample(frame_map,history_stream,snapshot,ego,lead,*,road_id,
                  ego_lane_id,lead_lane_id,surface_condition,traffic_actor_ids,
                  lane_change_started):
    frame,time=snapshot.frame,snapshot.timestamp.elapsed_seconds
    if type(lane_change_started) is not bool:raise ValueError('Missing lane change state')
    ego_row=_actor_row(ego,ego_lane_id);lead_row=_actor_row(lead,lead_lane_id)
    history={'frame':frame,'time_s':time,'road_id':road_id,
             'ego':ego_row,'lead':lead_row,'surface_condition':surface_condition,
             'traffic_actor_ids':list(traffic_actor_ids),'lane_change_started':lane_change_started}
    mapping=frame_map.append(frame,time)
    history_stream.write(json.dumps(history,allow_nan=False)+'\n')
    return {'video_frame':mapping['video_frame'],'history':history}
