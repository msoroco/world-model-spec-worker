"""Source-bound 80 mph diagnostic on a left-turn route."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES=600
HZ=20
MPH_PER_MPS=2.2369362921
LIMIT_MPH=80
CAMERAS=('overview','approach','reference_corner','driver_reference')

def check_config(config,road_text):
 prefix='training__C329610__NRS-484B-600-1e__motor_vehicle_driver__'
 if (config.get('case_id') not in (prefix+'probe_a',prefix+'probe_at',prefix+'probe_b')
     or config.get('law_id')!='NRS-484B-600-1e'
     or config.get('cell_id')!='C329610'
     or config.get('actor')!='motor_vehicle_driver'
     or config.get('duration_s')!=30 or config.get('rate_hz')!=HZ
     or config.get('frames')!=FRAMES or config.get('legal_verdict') is not None
     or config.get('physical_completion') not in (False, {})):
  raise ValueError('Exact C329610 scope or duration differs')
 if tuple(x.get('name') for x in config.get('cameras',()))!=CAMERAS:
  raise ValueError('Four named source cameras required')
 if any(x.get('fps')!=HZ or not all(x.get(k) for k in
        ('width','height','fov_deg','location_xyz_m','rotation_pyr_deg'))
        for x in config['cameras']):
  raise ValueError('Source camera geometry incomplete')
 root=ET.fromstring(road_text)
 roads={int(r.get('id')):r for r in root.findall('road')}
 if set(roads)!={1,2,3,4,13}:
  raise ValueError('Connected two-way left-turn roads missing')
 approach=roads[1].find('./planView/geometry')
 turn=roads[13].find('./planView/geometry')
 if (approach is None or approach.find('line') is None
     or float(approach.get('x'))!=-430 or float(approach.get('length'))!=423
     or turn is None or turn.find('arc') is None
     or not math.isclose(float(turn.find('arc').get('curvature')),1/7)):
  raise ValueError('Long approach or left-turn geometry differs')
 junction=root.find('junction')
 if junction is None or junction.get('id')!='100' or not any(
     c.get('incomingRoad')=='1' and c.get('connectingRoad')=='13'
     for c in junction.findall('connection')):
  raise ValueError('Left-turn lane connection absent')
 return {'case_id':config['case_id'],'frames':FRAMES,'source_cameras':list(CAMERAS),
         'authored_left_turn_geometry':True,'original_speed_observed':False,
         'physical_completion':False,'carla_contacted':False}

def measure(rows,source_kind):
 if source_kind not in ('authored_native_request','original_native'):
  raise ValueError('Unknown speed source')
 if len(rows)!=FRAMES:raise ValueError('Full 600-frame speed source required')
 speeds=[];roads=[];previous=None
 for i,row in enumerate(rows):
  if (row.get('frame')!=i or abs(row.get('time_s',-1)-(i+1)/HZ)>1e-8
      or row.get('source_kind')!=source_kind):
   raise ValueError('Original frame/time/source join differs')
  xyz=row.get('ego_center_xyz_m');velocity=row.get('ego_velocity_xyz_mps')
  if (not isinstance(xyz,list) or len(xyz)!=3 or
      not isinstance(velocity,list) or len(velocity)!=3 or
      not all(isinstance(v,(int,float)) and math.isfinite(v) for v in xyz+velocity)):
   raise ValueError('Original position or velocity missing')
  speed=math.sqrt(sum(v*v for v in velocity))*MPH_PER_MPS
  if row.get('road_id') not in (1,13,4):
   raise ValueError('Left-turn road join missing')
  if previous is not None and math.dist(xyz,previous)>3:
   raise ValueError('Discontinuous trajectory source')
  previous=xyz;speeds.append(speed);roads.append(row['road_id'])
 if not {1,13,4}<=set(roads):
  raise ValueError('Approach, left-turn arc and exit not all covered')
 return {'format':'c329610-left-turn-speed-meter-v1','source_kind':source_kind,
         'frames':FRAMES,'maximum_speed_mph':max(speeds),
         'frames_greater_than_80_mph':sum(v>LIMIT_MPH for v in speeds),
         'route_road_ids':list(dict.fromkeys(roads)),
         'original_native_observed':source_kind=='original_native',
         'physical_completion':False,'legal_verdict':None}

def read_and_measure(path,kind):
 return measure([json.loads(x) for x in Path(path).read_text().splitlines()],kind)
