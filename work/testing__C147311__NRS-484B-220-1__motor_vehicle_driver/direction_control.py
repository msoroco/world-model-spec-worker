"""CARLA-independent route follower for both directions of the same lane."""
import math


def _finite_pair(values, label):
 if not isinstance(values,(list,tuple)) or len(values)!=2:
  raise ValueError('Invalid '+label)
 if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
  raise ValueError('Nonfinite '+label)
 return float(values[0]),float(values[1])


class RouteFollower:
 def __init__(self, route_xy_m, *, target_speed_mps=4.0, reach_m=2.0):
  if not isinstance(route_xy_m,list) or len(route_xy_m)<2:
   raise ValueError('Route needs at least two points')
  self.route=[_finite_pair(p,'route point') for p in route_xy_m]
  if target_speed_mps<=0 or not math.isfinite(target_speed_mps):
   raise ValueError('Invalid target speed')
  if reach_m<=0 or not math.isfinite(reach_m):raise ValueError('Invalid waypoint reach')
  if any(math.dist(a,b)<0.1 for a,b in zip(self.route,self.route[1:])):
   raise ValueError('Duplicate route points')
  self.speed=float(target_speed_mps);self.reach=float(reach_m);self.index=1

 def step(self, position_xy_m, forward_xy, speed_mps):
  px,py=_finite_pair(position_xy_m,'position')
  fx,fy=_finite_pair(forward_xy,'forward')
  fn=math.hypot(fx,fy)
  if fn<0.1:raise ValueError('Zero vehicle forward')
  if type(speed_mps) not in (int,float) or not math.isfinite(speed_mps) or speed_mps<0:
   raise ValueError('Invalid observed speed')
  while self.index<len(self.route)-1 and math.dist((px,py),self.route[self.index])<=self.reach:
   self.index+=1
  tx,ty=self.route[self.index];vx,vy=tx-px,ty-py
  distance=math.hypot(vx,vy)
  if distance<=self.reach and self.index==len(self.route)-1:
   return {'throttle':0.0,'brake':1.0,'steer':0.0,'target_index':self.index,
           'route_complete':True,'target_distance_m':distance}
  if distance<0.1:raise ValueError('Route target coincides with vehicle')
  # Signed planar angle is positive for a target to the vehicle's left.
  angle=math.atan2(fx*vy-fy*vx,fx*vx+fy*vy)
  steer=max(-1.0,min(1.0,angle/math.radians(40)))
  error=self.speed-float(speed_mps)
  return {'throttle':max(0.0,min(0.45,0.12*error)),
          'brake':max(0.0,min(0.6,-0.2*error)),
          'steer':steer,'target_index':self.index,'route_complete':False,
          'target_distance_m':distance}
