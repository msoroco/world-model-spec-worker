"""Observed-state straight-route research controller; no legal judgment rule.

Engineering stationary detection schedules actions only. Raw movement determines
what was measured; no speed epsilon or hold span defines statutory cessation.
"""
import math

class Stop257Controller:
 def __init__(self,initial_target_y,stop_center_x=-13.8,stop_mode='stop'):
  self.initial_target_y=initial_target_y;self.stop_center_x=stop_center_x;self.stop_mode=stop_mode;self.phase='approach';self.stable=0;self.reference=None;self.events=[];self.integral={};self.last_speed={};self.acceleration={}
 def transition(self,phase,time_s):
  self.events.append({'time_s':time_s,'from':self.phase,'to':phase});self.phase=phase
 def command(self,role,state,target,axis,direction,maxspeed):
  position=state['position_m'][axis];remaining=direction*(target-position);speed=state['speed_mps'];requested=min(maxspeed,math.sqrt(2*1.5*max(0,remaining-.03)))
  previous=self.last_speed.get(role,speed);self.last_speed[role]=speed;acc=.8*self.acceleration.get(role,0)+.2*(speed-previous)/.05;self.acceleration[role]=acc
  error=requested-(speed+.15*max(0,acc));integral=self.integral.get(role,0)
  if error<0:integral=0
  integral=max(-3,min(3,integral+error*.05));self.integral[role]=integral;effort=.8*error+.08*integral
  desired_yaw=0 if axis==0 else -math.pi/2
  yaw=math.radians(state['heading_deg']);heading_error=(desired_yaw-yaw+math.pi)%(2*math.pi)-math.pi
  lateral_error=(state['position_m'][1]-1.75) if axis==0 else (state['position_m'][0]-1.75)
  steer=max(-.3,min(.3,1.5*heading_error-.2*lateral_error))
  result={'throttle':max(0,min(.6 if speed<requested-.5 else .2,effort)),'brake':max(0,min(1,-effort)),'steer':steer,'hand_brake':False,'requested_speed_mps':requested,'target_axis_m':target}
  if remaining<.05 or requested==0:result.update(throttle=0,brake=1,hand_brake=speed<.03)
  return result
 def step(self,time_s,states):
  ego,initial,further=[states[n] for n in ['ego','initial_through','further_through']]
  if self.phase=='approach':
   settled=all(s['speed_mps']<.03 for s in states.values()) and abs(ego['position_m'][0]-self.stop_center_x)<.2 and abs(initial['position_m'][1]-self.initial_target_y)<.2 and abs(further['position_m'][1]-70)<.2
   self.stable=self.stable+1 if settled else 0
   if self.stable>=4:self.reference={'time_s':time_s,'states':states};self.transition('initial_progress',time_s)
  if self.phase=='initial_progress' and max(v[1] for v in initial['body_vertices_m'])<-8:self.transition('subject_progress',time_s)
  if self.phase=='subject_progress' and min(v[0] for v in ego['body_vertices_m'])>8:self.transition('further_progress',time_s)
  targets={'ego':(self.stop_center_x if self.phase in ['approach','initial_progress'] else 24,0,1,5),'initial_through':(self.initial_target_y if self.phase=='approach' else -40,1,-1,5),'further_through':(70 if self.phase=='approach' else -24,1,-1,5)}
  commands={role:self.command(role,state,*targets[role]) for role,state in states.items()}
  if self.phase=='subject_progress':commands['further_through'].update(throttle=0,brake=1,hand_brake=further['speed_mps']<.03,requested_speed_mps=0)
  return commands
