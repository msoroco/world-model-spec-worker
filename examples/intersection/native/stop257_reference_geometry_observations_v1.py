"""Before-motion original Native footway and crossing evidence, no legal verdict."""
import json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path

def capture(carla,world,mapping,out,branch,markings):
 if branch not in ['no_line_marked_near_side_crosswalk','no_line_unmarked_sidewalk_connection_crosswalk']:raise ValueError('Unsupported branch')
 out=Path(out);xml=ET.parse(out/'road.xodr').getroot();west=next(r for r in xml.findall('road') if r.attrib['id']=='1');west_objects=[dict(v.attrib) for v in west.findall('./objects/object')];
 if any('stopline' in (v.get('name','')+v.get('type','')).lower().replace('_','') or v.get('id')=='1001' for v in west_objects):raise ValueError('Unexpected applicable West stop line map object')
 points=[]
 for x in [-8.6,-8.49,-7.75,-7.01,-6.99]:
  for y in [-8,-7.01,-6.99,6.99,7.01,8]:
   hits=world.cast_ray(carla.Location(x=x,y=y,z=5),carla.Location(x=x,y=y,z=-5));values=[{'label':str(h.label),'native_xyz_m':[h.location.x,h.location.y,h.location.z]} for h in hits];points.append({'xy_m':[x,y],'all_hits':values,'topmost':max(values,key=lambda v:v['native_xyz_m'][2]) if values else None})
 byxy={tuple(v['xy_m']):v for v in points};endpoints=[]
 for road,station in [(3,392.99),(4,.01)]:
  wp=mapping.get_waypoint_xodr(road,3,station)
  if wp is None or wp.lane_type!=carla.LaneType.Sidewalk:raise ValueError('Actual Native lateral sidewalk connection missing')
  endpoints.append({'road_id':road,'lane_id':3,'station_m':station,'lane_type':str(wp.lane_type),'native_xyz_m':[wp.transform.location.x,wp.transform.location.y,wp.transform.location.z],'lane_width_m':wp.lane_width})
 for x in [-8.49,-7.75,-7.01]:
  for sign in [-1,1]:
   outer=byxy[(x,sign*7.01)]['topmost'];inner=byxy[(x,sign*6.99)]['topmost']
   if outer is None or inner is None or not .14<outer['native_xyz_m'][2]-inner['native_xyz_m'][2]<.17:raise ValueError('Actual topmost sidewalk/roadway step not established')
 if any(abs(v['native_xyz_m'][0]+7.75)>1e-3 or abs(v['lane_width_m']-1.5)>1e-3 for v in endpoints):raise ValueError('Sidewalk band geometry differs')
 original_map_points=[[p.x,p.y,p.z] for p in mapping.get_crosswalks()];zebra=[v for v in markings if 'crosswalk_stripe_' in v['role']];westline=[v for v in markings if '_west_physical_stopline_' in v['role']]
 if westline:raise ValueError('Unexpected applicable West stop line')
 marked=branch=='no_line_marked_near_side_crosswalk'
 if marked and (len(zebra)!=80 or not original_map_points):raise ValueError('Incomplete marked crosswalk realization')
 if not marked and (zebra or original_map_points):raise ValueError('Unexpected marked crosswalk registry or physical tiles')
 result={'kind':'original_before_motion_reference_geometry','branch':branch,'source_map_sha256':hashlib.sha256((out/'road.xodr').read_bytes()).hexdigest(),'footway_endpoints':endpoints,'topmost_survey':points,'Native_marked_registry_points':original_map_points,'actual_marked_tiles':zebra,'crosswalk_band_native_xy_m':[[-8.5,-7],[-7,-7],[-7,7],[-8.5,7]],'band_derivation':'Opposite actual 1.5m-wide sidewalk lateral connections centered x=-7.75, with Native topmost sidewalk/roadway steps at y±7. Actual paint tiles independently retained for marked branch. SDK marked envelope remains separate.','actual_west_map_objects':west_objects,'negative_scope':'No applicable West stopline object in frozen map and no physical West stopline tile; East stopline is absent in independently inventoried one-STOP world','painted_absence_proves_unmarked_absence':False,'statutory_classification_provenance':'Local application of supplied crosswalk definition to actual sidewalk lateral connections; no Native SDK unmarked-crosswalk registry claimed','source_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'nearest_viewpoint_claimed':False}
 with (out/'native-reference-geometry-before-motion.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 return result
