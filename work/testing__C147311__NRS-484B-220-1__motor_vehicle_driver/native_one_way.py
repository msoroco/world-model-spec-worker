"""Native lane inventory for one-way multilane route; signage needs source review."""
def verify_multilane_one_way(world,road_id,lane_ids,*,spacing_m=2.0):
 if len(set(lane_ids))<2:raise ValueError('Two driving lanes required')
 observed={wp.lane_id for wp in world.get_map().generate_waypoints(spacing_m) if wp.road_id==road_id and str(wp.lane_type).lower().endswith('driving')}
 if not set(lane_ids)<=observed:raise ValueError('Selected Native driving lanes missing')
 if any(i>0 for i in lane_ids) and any(i<0 for i in lane_ids):raise ValueError('Selected lanes include opposing Native directions')
 return {'road_id':road_id,'selected_lane_ids':sorted(set(lane_ids)),'designation_and_signpost_status':'source review required'}
