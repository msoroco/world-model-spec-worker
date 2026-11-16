"""Native lane inventory and paired route construction for a one-way comparison.

The authority designation and installed signs must be supplied separately. Native
lane topology alone cannot establish either legal fact.
"""
import math
from pathlib import Path
import importlib.util

def verify_multilane_one_way(world,road_id,lane_ids,*,spacing_m=2.0):
 if len(set(lane_ids))<2:raise ValueError('Two driving lanes required')
 observed={wp.lane_id for wp in world.get_map().generate_waypoints(spacing_m) if wp.road_id==road_id and str(wp.lane_type).lower().endswith('driving')}
 if not set(lane_ids)<=observed:raise ValueError('Selected Native driving lanes missing')
 if any(i>0 for i in lane_ids) and any(i<0 for i in lane_ids):raise ValueError('Selected lanes include opposing Native directions')
 return {'road_id':road_id,'selected_lane_ids':sorted(set(lane_ids)),'designation_and_signpost_status':'source review required'}


def paired_route_points(world, road_id, lane_ids, designated_forward_xy, *,
                        travel_lane_id, min_span_m=12.0, spacing_m=2.0):
 """Return opposing travel routes on the *same* Native driving lane.

 This is a construction plan, not proof that CARLA will realize the wrong-way
 trajectory. Coordinates come from sampled Native waypoints; an operator must
 bind the designation and signs to reviewed site sources before capture.
 """
 verify_multilane_one_way(world, road_id, lane_ids, spacing_m=spacing_m)
 if travel_lane_id not in lane_ids:
  raise ValueError('Travel lane is not in selected one-way lanes')
 if len(designated_forward_xy)!=2 or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in designated_forward_xy):
  raise ValueError('Invalid designated direction')
 dx,dy=map(float,designated_forward_xy)
 norm=math.hypot(dx,dy)
 if norm==0:raise ValueError('Zero designated direction')
 dx,dy=dx/norm,dy/norm
 waypoints=[wp for wp in world.get_map().generate_waypoints(spacing_m)
            if wp.road_id==road_id and wp.lane_id==travel_lane_id
            and str(wp.lane_type).lower().endswith('driving')]
 if len(waypoints)<2:raise ValueError('Insufficient Native route waypoints')
 points=[]
 for wp in waypoints:
  location=wp.transform.location
  x,y=float(location.x),float(location.y)
  if not math.isfinite(x) or not math.isfinite(y):raise ValueError('Nonfinite Native waypoint')
  points.append((x*dx+y*dy,x,y))
 points.sort()
 if points[-1][0]-points[0][0]<min_span_m:
  raise ValueError('Native route span too short')
 # Collapse duplicated projections, which can arise at junction waypoint samples.
 route=[]
 for progress,x,y in points:
  if not route or progress-route[-1][0]>0.1:route.append((progress,x,y))
 if len(route)<2:raise ValueError('Native route has no distinct progression')
 forward=[[x,y] for _,x,y in route]
 return {'road_id':road_id,'lane_id':travel_lane_id,
         'designated_forward_xy':[dx,dy],
         'with_designation_xy_m':forward,
         'against_designation_xy_m':list(reversed(forward)),
         'span_m':route[-1][0]-route[0][0],
         'designation_and_signpost_status':'source review required'}


def prepare_reviewed_route(world, packet, source_root, *, travel_lane_id, min_span_m=12.0):
 """Join hashed site sources to the exact Native lane route before capture."""
 spec=importlib.util.spec_from_file_location('one_way_site_review',Path(__file__).with_name('site_review.py'))
 module=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(module)
 map_id=world.get_map().name
 review=module.validate(packet,source_root,expected_map_id=map_id,
                             road_id=packet['road_id'],lane_ids=packet['driving_lane_ids'])
 route=paired_route_points(world,packet['road_id'],packet['driving_lane_ids'],
                           packet['designated_forward_xy'],
                           travel_lane_id=travel_lane_id,min_span_m=min_span_m)
 return {'site_review':review,'routes':route}
