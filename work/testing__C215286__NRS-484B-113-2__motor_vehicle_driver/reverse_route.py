"""Straight Native reverse targets for matched crosswalk comparisons.

Target distances are engineering construction inputs. The saved original body
history, not these targets, determines whether backing actually overlapped.
"""
import math
import importlib.util
from pathlib import Path
from shapely.affinity import translate
from shapely.geometry import MultiPoint,Polygon


def _axis(forward_xy):
 if not isinstance(forward_xy,(list,tuple)) or len(forward_xy)!=2:
  raise ValueError('Vehicle forward axis required')
 if any(type(v) not in (int,float) or not math.isfinite(v) for v in forward_xy):
  raise ValueError('Nonfinite vehicle forward axis')
 fx,fy=map(float,forward_xy);norm=math.hypot(fx,fy)
 if norm<0.1:raise ValueError('Zero vehicle forward axis')
 return fx/norm,fy/norm


def validate_pair(start_body_xy,forward_xy,crosswalk_polygon_xy,
                  *,over_distance_m,short_distance_m):
 """Require distinct target complete-body geometries on the same approach."""
 fx,fy=_axis(forward_xy)
 body=MultiPoint(start_body_xy).convex_hull
 crossing=Polygon(crosswalk_polygon_xy)
 if body.area<=0 or not crossing.is_valid or crossing.area<=0:
  raise ValueError('Invalid route body or crosswalk geometry')
 if body.intersects(crossing):raise ValueError('Reverse start body already overlaps crosswalk')
 for distance in (over_distance_m,short_distance_m):
  if type(distance) not in (int,float) or not math.isfinite(distance) or distance<=0:
   raise ValueError('Positive finite reverse target distance required')
 over=translate(body,xoff=-fx*over_distance_m,yoff=-fy*over_distance_m)
 short=translate(body,xoff=-fx*short_distance_m,yoff=-fy*short_distance_m)
 if not over.intersects(crossing):raise ValueError('Over target body misses crosswalk')
 if short.intersects(crossing):raise ValueError('Short target body overlaps crosswalk')
 if over_distance_m<=short_distance_m:
  raise ValueError('Over target must follow short target on same reverse route')
 return {'forward_xy':[fx,fy],
         'over_distance_m':float(over_distance_m),
         'short_distance_m':float(short_distance_m),
         'start_body_clear':True,
         'target_geometry':'constructed only; original motion unverified'}


def prepare_reviewed_pair(packet,source_root,start_body_xy,forward_xy,
                          *,over_distance_m,short_distance_m,
                          native_map_id,road_id,crosswalk_id):
 """Bind source docs and Native identities before constructing both targets."""
 spec=importlib.util.spec_from_file_location('reverse_site_review',Path(__file__).with_name('site_review.py'))
 site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)
 review=site.validate(packet,source_root,native_map_id=native_map_id,
                      road_id=road_id,crosswalk_id=crosswalk_id)
 targets=validate_pair(start_body_xy,forward_xy,packet['crosswalk_polygon_xy_m'],
                       over_distance_m=over_distance_m,
                       short_distance_m=short_distance_m)
 return {'site_review':review,'targets':targets}


class ReverseTargetController:
 def __init__(self,origin_xy,forward_xy,target_distance_m,*,stop_window_m=0.25,
              assumed_deceleration_mps2=1.5):
  if not isinstance(origin_xy,(list,tuple)) or len(origin_xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in origin_xy):
   raise ValueError('Finite reverse origin required')
  self.origin=tuple(map(float,origin_xy));self.forward=_axis(forward_xy)
  if type(target_distance_m) not in (int,float) or not math.isfinite(target_distance_m) or target_distance_m<=0:
   raise ValueError('Positive finite target distance required')
  if stop_window_m<=0 or not math.isfinite(stop_window_m):raise ValueError('Invalid stop window')
  if assumed_deceleration_mps2<=0 or not math.isfinite(assumed_deceleration_mps2):
   raise ValueError('Invalid assumed reverse deceleration')
  self.target=float(target_distance_m);self.window=float(stop_window_m)
  self.deceleration=float(assumed_deceleration_mps2)

 def step(self,center_xy,speed_mps):
  if not isinstance(center_xy,(list,tuple)) or len(center_xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in center_xy):
   raise ValueError('Finite body center required')
  if type(speed_mps) not in (int,float) or not math.isfinite(speed_mps) or speed_mps<0:
   raise ValueError('Finite nonnegative speed required')
  dx=float(center_xy[0])-self.origin[0];dy=float(center_xy[1])-self.origin[1]
  progress=-(dx*self.forward[0]+dy*self.forward[1])
  remaining=self.target-progress
  stopping_distance=float(speed_mps)**2/(2*self.deceleration)
  if remaining<=self.window+stopping_distance:
   return {'reverse':True,'throttle':0.0,'brake':1.0,
           'target_reached':remaining<=self.window,
           'reverse_progress_m':progress,'remaining_m':remaining}
  # Reduce throttle on approach; actual stopping remains a physical check.
  throttle=min(0.25,max(0.07,0.08*remaining-0.04*float(speed_mps)))
  return {'reverse':True,'throttle':throttle,'brake':0.0,'target_reached':False,
          'reverse_progress_m':progress,'remaining_m':remaining}
