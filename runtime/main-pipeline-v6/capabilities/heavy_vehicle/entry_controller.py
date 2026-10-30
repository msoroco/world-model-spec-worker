"""Prospective actual-state passenger overtaker controls and finite entry geometry.
No CARLA import, simulator connection, legal threshold or Nativefeasibility claim.
"""
import math
from dataclasses import dataclass
from following_controller import along_route_body_gap,body_references,tangent_speed

def clamp(v,a,b):return max(a,min(b,v))
def smooth(t):
 u=clamp(t,0.,1.);return u*u*(3.-2.*u)
def wrap(a):return (a+math.pi)%(2*math.pi)-math.pi

def geometry(ego,lead,car):
 a=body_references(ego['body_vertices_native_m']);b=body_references(lead['body_vertices_native_m']);c=body_references(car['body_vertices_native_m']);verts=car['body_vertices_native_m'];inside_lane=all(0<=v[1]<=12 for v in verts);inside_interval=c['rear_route_m']>=a['front_route_m'] and c['front_route_m']<=b['rear_route_m'];overlap_lane=max(v[1] for v in verts)>=0 and min(v[1] for v in verts)<=12
 return {'car_actor_id':car['actor_id'],'car_rear_after_ego_front_m':c['rear_route_m']-a['front_route_m'],'lead_rear_after_car_front_m':b['rear_route_m']-c['front_route_m'],'car_full_body_inside_lane_minus1':inside_lane,'car_any_body_overlaps_lane_minus1':overlap_lane,'car_full_body_between_truck_route_references':inside_interval,'car_full_body_occupies_space':inside_lane and inside_interval,'car_body_route_interval_m':[c['rear_route_m'],c['front_route_m']],'truck_space_route_interval_m':[a['front_route_m'],b['rear_route_m']],'actual_nearest_front_actor_id':car['actor_id'] if overlap_lane and c['rear_route_m']>=a['front_route_m'] else lead['actor_id'],'designated_truck_reference_actor_id':lead['actor_id'],'convention':'Finite all8actualNativebodyvertex routeextrema andnative straightlane-1 y0..12; engineeringnearest-frontselector, NOT legalfollowing/immediacy/dangerdefinition'}

@dataclass
class EntryCarController:
 cruise_reference_mps:float=18.
 entry_offset_reference_m:float=30.
 initial_follow_gap_m:float=20.
 lane_change_seconds:float=4.
 integral_speed_error:float=0.
 merge_start_s:object=None
 last_frame:int=-1

 def step(self,frame,time_s,car,ego,lead):
  assert frame>self.last_frame and len({car['actor_id'],ego['actor_id'],lead['actor_id']})==3
  self.last_frame=frame;g=geometry(ego,lead,car);v=tangent_speed(car['position_m'],car['velocity_mps']);ev=tangent_speed(ego['position_m'],ego['velocity_mps']);gap=along_route_body_gap(car['body_vertices_native_m'],ego['body_vertices_native_m']);phase='follow';desired_y=6.;dy=0.
  if time_s>=20:
   if self.merge_start_s is None and g['car_rear_after_ego_front_m']>=self.entry_offset_reference_m and car['position_m'][1]<0:self.merge_start_s=time_s
   if self.merge_start_s is None:
    phase='left_pass';u=clamp((time_s-20)/self.lane_change_seconds,0,1);desired_y=6.-12.*smooth(u);dy=-12.*6*u*(1-u)/self.lane_change_seconds
   else:
    phase='merge' if time_s-self.merge_start_s<self.lane_change_seconds else 'occupy';u=clamp((time_s-self.merge_start_s)/self.lane_change_seconds,0,1);desired_y=-6.+12.*smooth(u);dy=12.*6*u*(1-u)/self.lane_change_seconds
  if time_s<2:requested=0.
  elif phase=='follow':requested=clamp(ev+.65*(gap-self.initial_follow_gap_m)+.5*(ev-v),0,self.cruise_reference_mps)
  elif phase=='left_pass':requested=self.cruise_reference_mps
  else:requested=clamp(ev+.65*(self.entry_offset_reference_m-g['car_rear_after_ego_front_m'])+.5*(ev-v),0,self.cruise_reference_mps)
  trial=clamp(self.integral_speed_error+.05*(requested-v),-5.,5.);output=.28+.5*(requested-v)+.12*trial
  if not ((output>1 and requested>v) or (output<-1 and requested<v)):self.integral_speed_error=trial
  output=.28+.5*(requested-v)+.12*self.integral_speed_error;throttle=clamp(output,0,1);brake=clamp(-output,0,1)
  if time_s<2 or time_s>=34:throttle=0.;brake=.7
  if phase=='follow' and gap<6:throttle=0.;brake=1.
  yaw=math.radians(car['heading_deg']);desired_heading=math.atan2(dy,max(abs(car['velocity_mps'][0]),2.));steer=clamp(1.2*wrap(desired_heading-yaw)+.15*(desired_y-car['position_m'][1]),-.6,.6)
  return {'throttle':throttle,'brake':brake,'steer':steer,'hand_brake':(time_s<2 or time_s>=34) and abs(v)<.05,'phase':phase,'requested_speed_mps':requested,'desired_y_m':desired_y,'desired_heading_rad':desired_heading,'merge_start_s':self.merge_start_s,'geometry':g,'actual_inputs':{'frame':frame,'time_s':time_s,'car':car,'ego':ego,'designated_lead_truck':lead},'integral_speed_error':self.integral_speed_error,'scope':'Engineeringmotioncontrol only; actualstates/controls/nativeoutcome mandatory, no legaljudgment or createdobservation'}
