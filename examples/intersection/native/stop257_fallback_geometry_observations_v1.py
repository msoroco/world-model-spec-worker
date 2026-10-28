"""Native no-line/no-crosswalk geometry and nearest-boundary candidate, not a verdict."""
import json,hashlib,math,xml.etree.ElementTree as ET
from pathlib import Path

def capture(carla,world,mapping,out,markings):
 out=Path(out);xml=ET.parse(out/'road.xodr').getroot();west=next(v for v in xml.findall('road') if v.attrib['id']=='1')
 if west.findall('./objects/object') or xml.findall('.//lane[@type="sidewalk"]') or xml.findall('.//object[@type="crosswalk"]'):raise ValueError('Generated no-line/no-crosswalk branch contradicted by whole map')
 if mapping.get_crosswalks() or any(mapping.get_waypoint_xodr(road,3,station) is not None for road,station in [(3,392.99),(4,.01)]):raise ValueError('Native marked registry or actual footway connections present')
 if bool(markings):raise ValueError('Unexpected physical marking in fallback approach')
 lanes=[];edges=[]
 for road,station in [(3,390),(4,3)]:
  samples=[]
  for lane in [-2,-1,1,2]:
   wp=mapping.get_waypoint_xodr(road,lane,station)
   if wp is None or wp.lane_type!=carla.LaneType.Driving:raise ValueError('Missing actual crossing-road driving lane')
   t=wp.transform;forward=t.get_forward_vector();norm=math.hypot(forward.x,forward.y);normal=(-forward.y/norm,forward.x/norm);points=[[t.location.x+sign*wp.lane_width/2*normal[0],t.location.y+sign*wp.lane_width/2*normal[1],t.location.z] for sign in [-1,1]];samples.extend(points);lanes.append({'road_id':road,'lane_id':lane,'station_m':station,'actual_native_pose':str(t),'width_m':wp.lane_width,'edge_points_native_m':points})
  edge=min(p[0] for p in samples);edges.append(edge)
 if abs(edges[0]-edges[1])>1e-4:raise ValueError('Opposite actual crossing-road edges not connected/aligned')
 edge=edges[0];rays=[]
 for y in [-10,10]:
  for offset in [-.01,.01]:
   x=edge+offset;hits=world.cast_ray(carla.Location(x=x,y=y,z=5),carla.Location(x=x,y=y,z=-5));values=[{'label':str(h.label),'native_xyz_m':[h.location.x,h.location.y,h.location.z]} for h in hits];top=max(values,key=lambda v:v['native_xyz_m'][2]) if values else None
   if offset<0 and values:raise ValueError('Unexpected topmost surface outside actual through roadway')
   if offset>0 and (top is None or abs(top['native_xyz_m'][2])>.01):raise ValueError('Missing topmost roadway surface inside actual through road')
   rays.append({'xy_m':[x,y],'all_hits':values,'topmost':top})
 whole=[{'actor_id':a.id,'type_id':a.type_id,'role':a.attributes.get('role_name')} for a in world.get_actors()]
 if any(v['type_id'].startswith(('vehicle.','walker.','controller.')) for v in whole):raise ValueError('Geometry must be observed before vehicle spawn')
 result={'kind':'original_before_motion_neither_line_nor_crosswalk_geometry','branch':'neither_line_nor_crosswalk_nearest_viewpoint_candidate','source_map_sha256':hashlib.sha256((out/'road.xodr').read_bytes()).hexdigest(),'actual_through_lane_edges':lanes,'topmost_boundary_rays':rays,'actual_before_vehicle_whole_world_actor_inventory':whole,'Native_marked_registry_points':[],'Native_sidewalk_endpoints_present':False,'actual_physical_marking_tiles':markings,'nearest_candidate_native_x_m':edge,'candidate_derivation':'Prolonged actual crossing-road driving-lane lateral edges at both sides of the intersection, corroborated by before-motion topmost surface/void brackets; not Native junction bounding box. Candidate is nearest connected inbound boundary outside intersection for vehicle leading body; actual modeled-view support must be measured.','absence_scope':'Whole generated map/Native endpoint queries/topmost surfaces and all physical road-marking actors; empty marked registry alone is insufficient','modeled_driver_reference_local_m':[0,0,1.5],'anatomical_driver_eye_observed':False,'human_perception_observed':False,'nearest_relevant_viewpoint_established':False,'legal_compliance_established':False,'source_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 with (out/'native-fallback-geometry-before-motion.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 return result
