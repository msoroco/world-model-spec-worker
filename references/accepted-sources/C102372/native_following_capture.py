"""Prospective tick-neutral native two-actor capture helper; never connects or drives."""
import math
from footprint_gap import gap

def snapshot(actor):
 from original_observations import actor_state
 state=actor_state(actor);pose=actor.get_transform();box=actor.bounding_box
 local=[[p.x,p.y,p.z] for p in box.get_local_vertices()];matrix=pose.get_matrix();native=state['body_vertices_m']
 predicted=[[sum(matrix[row][col]*([*p,1][col]) for col in range(4)) for row in range(3)] for p in local]
 error=max(min(math.dist(p,q) for q in native) for p in predicted)
 if len(native)!=8 or error>1e-4:raise ValueError('Native body vertices/offset/rotation differ from actual instance pose')
 state.update(body_vertices_native_m=native,body_local_vertices_m=local,pose_native_matrix=matrix,
  native_box_extent_m=[box.extent.x,box.extent.y,box.extent.z],native_box_offset_m=[box.location.x,box.location.y,box.location.z],native_box_rotation_deg={'yaw':box.rotation.yaw,'pitch':box.rotation.pitch,'roll':box.rotation.roll},native_pose_check_maximum_error_m=error)
 control=actor.get_control();state['applied_control']={k:getattr(control,k) for k in ('throttle','brake','steer','hand_brake','reverse','manual_gear_shift','gear','speed','jump') if hasattr(control,k)}
 if hasattr(control,'direction'):state['applied_control']['direction']=[control.direction.x,control.direction.y,control.direction.z]
 return state

def capture_pair(ego,apparatus,frame,time_s,actual_follower_inputs):
 if ego.id==apparatus.id:raise ValueError('Distinct native subject and apparatus required')
 a,b=snapshot(ego),snapshot(apparatus)
 if a['blueprint']!='vehicle.carlamotors.carlacola' or b['blueprint']!='vehicle.carlamotors.carlacola':raise ValueError('Actual native assets differ from prospective comparison')
 distance=gap(a['body_vertices_native_m'],b['body_vertices_native_m'])
 packet={'frame':frame,'time_s':time_s,'ego':a,'apparatus':b,'native_nearest_footprint_gap_m':distance,
  'centre_distance_diagnostic_m':math.dist([sum(v[k] for v in a['body_vertices_native_m'])/8 for k in (0,1)],[sum(v[k] for v in b['body_vertices_native_m'])/8 for k in (0,1)]),
  'follower_controller_inputs':actual_follower_inputs,'response_purpose_native_observation':None,
  'siren_native_observation':None,'purpose_provenance':'Separate user-authored synthetic condition; neither model/lamp nor siren establishes purpose'}
 participant_row={'time_s':time_s,'value':{'frame':frame,'ego':a,'apparatus':b}}
 return packet,participant_row
