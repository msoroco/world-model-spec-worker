"""Source-bound angle-parking orientation diagnostic without a legal cutoff."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

FRAMES=600
HZ=20
VIEWS=('overview','approach','reference_corner','driver_reference')

def check_config(config,road_text):
 prefix='training__C385967__LVMC-11-52-070__motor_vehicle_driver__'
 if (config.get('case_id') not in (prefix+'probe_a',prefix+'probe_b')
     or config.get('law_id')!='LVMC-11-52-070'
     or config.get('cell_id')!='C385967' or config.get('actor')!='motor_vehicle_driver'
     or config.get('duration_s')!=30 or config.get('rate_hz')!=HZ
     or config.get('frames')!=FRAMES or config.get('physical_completion') != {}
     or config.get('legal_verdict') is not None):
  raise ValueError('C385967 exact scope or duration differs')
 if tuple(c.get('name') for c in config.get('cameras',()))!=VIEWS:
  raise ValueError('Four named source cameras required')
 if any(c.get('fps')!=HZ or not all(c.get(k) for k in
        ('width','height','fov_deg','location_xyz_m','rotation_pyr_deg'))
        for c in config['cameras']):
  raise ValueError('Source camera geometry incomplete')
 root=ET.fromstring(road_text);road=root.find('road')
 if road is None or road.get('id')!='1' or road.find('./planView/geometry/line') is None:
  raise ValueError('One-way road source missing')
 lanes={(l.get('id'),l.get('type')) for l in road.findall('./lanes/laneSection/right/lane')}
 if {('-1','driving'),('-2','parking'),('-3','sidewalk')}-lanes:
  raise ValueError('Angle parking lane source missing')
 if road.findall('./lanes/laneSection/left/lane'):
  raise ValueError('Opposing driving lane present')
 if not any(o.get('type')=='parkingSpace' for o in road.findall('objects/object')):
  raise ValueError('Angle bay marking source missing')
 if not any(s.get('name')=='ANGLE PARKING' for s in road.findall('signals/signal')):
  raise ValueError('Angle parking sign proposal missing')
 if not config.get('permission_source_required') or not config.get('original_activity_source_required'):
  raise ValueError('Administrative permission and parking activity source required')
 return {'case_id':config['case_id'],'frames':FRAMES,
         'source_cameras':list(VIEWS),'authored_one_way_bay':True,
         'engineer_permission_verified':False,'actual_parking_observed':False,
         'carla_contacted':False,'physical_completion':False}

def measure(rows,source_kind):
 if source_kind not in ('authored_native_request','original_native'):
  raise ValueError('Unknown source kind')
 if len(rows)!=FRAMES:raise ValueError('Full 600-frame source required')
 projections=[]
 for i,row in enumerate(rows):
  if (row.get('frame')!=i or abs(row.get('time_s',-1)-(i+1)/HZ)>1e-3
      or row.get('source_kind')!=source_kind):
   raise ValueError('Frame/time/source join differs')
  xy=row.get('ego_center_xy_m');yaw=row.get('ego_front_yaw_deg')
  speed=row.get('ego_speed_mps')
  if (not isinstance(xy,list) or len(xy)!=2 or
      not all(isinstance(v,(int,float)) and math.isfinite(v) for v in xy)
      or not isinstance(yaw,(int,float)) or not math.isfinite(yaw)
      or not isinstance(speed,(int,float)) or not math.isfinite(speed) or speed<0):
   raise ValueError('Original parked body pose or speed missing')
  if not 3.5<=xy[0]<=9.5 or not -3<=xy[1]<=3:
   raise ValueError('Requested center outside authored bay')
  if source_kind=='original_native' and not isinstance(row.get('parking_activity_review'),dict):
   raise ValueError('Original parking activity source missing')
  # The source road tangent points north. Positive/negative projection is a
  # clear engineered contrast, not a statutory angular tolerance.
  projections.append(math.sin(math.radians(yaw)))
 if min(projections)>0:return {'direction':'front_with_lawful_flow','projection_min':min(projections)}
 if max(projections)<0:return {'direction':'front_against_lawful_flow','projection_max':max(projections)}
 return {'direction':'mixed_or_unknown'}

def read_and_measure(path,kind):
 return measure([json.loads(x) for x in Path(path).read_text().splitlines()],kind)
