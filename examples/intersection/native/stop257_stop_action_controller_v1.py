"""Unselected stop-action construction draft; Native capability still required.

Both modes use the SAME traffic-only scheduling and downstream response policy.
The sole requested action difference is ego stop versus continuous slow roll at
and beyond the physical line until the common subject-progress event. No speed
request, stationary detector, or event phase defines statutory cessation.
"""
import math
from stop257_controller_v2 import Stop257Controller as Base

class Stop257Controller(Base):
 def __init__(self,initial_target_y,stop_center_x=-13.8,stop_mode='stop',rolling_speed_mps=.5,post_stop_speed_mps=5):
  if stop_mode not in ['stop','roll']:raise ValueError('Unknown stop action request')
  if not 0<rolling_speed_mps<5:raise ValueError('Rolling request outside draft envelope')
  super().__init__(initial_target_y,stop_center_x,stop_mode)
  self.rolling_speed_mps=rolling_speed_mps
  if not 0<post_stop_speed_mps<=5:raise ValueError("Post-stop request exceeds retained controller envelope")
  self.post_stop_speed_mps=post_stop_speed_mps
 def step(self,time_s,states):
  ego,initial,further=[states[n] for n in ['ego','initial_crossing','further_crossing']]
  if self.phase=='approach':
   # Deliberately independent of ego stopping behavior in BOTH modes.
   settled=(initial['speed_mps']<.03 and further['speed_mps']<.03
            and abs(initial['position_m'][1]-self.initial_target_y)<.2
            and abs(further['position_m'][1]-70)<.2)
   self.stable=self.stable+1 if settled else 0
   if self.stable>=4:
    self.reference={'time_s':time_s,'states':states};self.transition('initial_progress',time_s)
  if self.phase=='initial_progress' and max(v[1] for v in initial['body_vertices_m'])<-8:self.transition('subject_progress',time_s)
  if self.phase=='subject_progress' and min(v[0] for v in ego['body_vertices_m'])>8:self.transition('further_progress',time_s)
  ego_target=self.stop_center_x if self.phase in ['approach','initial_progress'] else 24
  ego_max=5 if self.phase in ["approach","initial_progress"] else self.post_stop_speed_mps
  if self.stop_mode=='roll' and self.phase in ['approach','initial_progress']:
   ego_target=24
   ego_max=(min(5,self.rolling_speed_mps+math.sqrt(3*max(0,self.stop_center_x-ego['position_m'][0])))
            if self.phase=='approach' else self.rolling_speed_mps)
  targets={'ego':(ego_target,0,1,ego_max),
           'initial_crossing':(self.initial_target_y if self.phase=='approach' else -40,1,-1,5),
           'further_crossing':(70 if self.phase=='approach' else -24,1,-1,5)}
  commands={role:self.command(role,state,*targets[role]) for role,state in states.items()}
  if self.phase=='subject_progress':commands['further_crossing'].update(throttle=0,brake=1,hand_brake=further['speed_mps']<.03,requested_speed_mps=0)
  return commands
