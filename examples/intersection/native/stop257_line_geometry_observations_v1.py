"""Before-motion actual line-first geometry; retain footways independently."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path

def capture(carla,world,mapping,out,markings):
 out=Path(out);xml=ET.parse(out/'road.xodr').getroot();west=next(r for r in xml.findall('road') if r.attrib['id']=='1');objects=[dict(v.attrib) for v in west.findall('./objects/object')];declared=[v for v in objects if v.get('id')=='1001'];tiles=[v for v in markings if '_west_physical_stopline_' in v['role']]
 if len(declared)!=1 or len(tiles)!=20 or len(markings)!=20:raise ValueError('Actual line-first original requires West physical line only; East entrance unsigned')
 if any(len(v['body_vertices_m'])!=8 for v in markings):raise ValueError('Physical line full Native body missing')
 edge=min(p[0] for t in tiles for p in t['body_vertices_m']);downstream=max(p[0] for t in tiles for p in t['body_vertices_m']);endpoints=[];surveys=[]
 for road,station in [(3,392.99),(4,.01)]:
  wp=mapping.get_waypoint_xodr(road,3,station)
  if wp is None or wp.lane_type!=carla.LaneType.Sidewalk:raise ValueError('Common line reference geometry must retain actual lateral footways')
  endpoints.append({'road_id':road,'lane_id':3,'station_m':station,'lane_type':str(wp.lane_type),'native_xyz_m':[wp.transform.location.x,wp.transform.location.y,wp.transform.location.z],'lane_width_m':wp.lane_width})
 for x in [-8.49,-7.75,-7.01]:
  for sign in [-1,1]:
   pair=[]
   for y in [sign*7.01,sign*6.99]:
    hits=[{'label':str(h.label),'native_xyz_m':[h.location.x,h.location.y,h.location.z]} for h in world.cast_ray(carla.Location(x=x,y=y,z=5),carla.Location(x=x,y=y,z=-5))];record={'xy_m':[x,y],'all_hits':hits,'topmost':max(hits,key=lambda h:h['native_xyz_m'][2]) if hits else None};surveys.append(record);pair.append(record['topmost'])
   if any(v is None for v in pair) or not .14<pair[0]['native_xyz_m'][2]-pair[1]['native_xyz_m'][2]<.17:raise ValueError('Actual topmost common lateral footways missing')
 result={'kind':'original_before_motion_line_first_geometry','branch':'stop_sign_marked_line','source_map_sha256':hashlib.sha256((out/'road.xodr').read_bytes()).hexdigest(),'source_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_west_map_objects':objects,'actual_West_line_tiles':tiles,'applicable_upstream_x_m':edge,'applicable_downstream_x_m':downstream,'footway_endpoints':endpoints,'topmost_survey':surveys,'Native_marked_registry_points':[[p.x,p.y,p.z] for p in mapping.get_crosswalks()],'crosswalk_band_native_xy_m':[[-8.5,-7],[-7,-7],[-7,7],[-8.5,7]],'priority':'Supplied257-1 clearly marked line comes first. Actual unmarked footway connection is retained and does not replace the present line. Separate450-2 hierarchy not applied.','legal_compliance_established':False}
 with (out/'native-line-geometry-before-motion.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 return result
