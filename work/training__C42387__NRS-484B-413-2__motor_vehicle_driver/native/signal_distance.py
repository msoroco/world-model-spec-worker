"""Exact business-district signal distance request meter."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

PREFIX='training__C42387__NRS-484B-413-2__motor_vehicle_driver__'
VIEWS=('overview','approach','turn_reference','driver_reference')
FEET_100_M=30.48


def check_config(config,road_text):
 if (config.get('case_id') not in (PREFIX+'probe_a',PREFIX+'probe_b')
     or config.get('law_id')!='NRS-484B-413-2' or config.get('cell_id')!='C42387'
     or config.get('actor')!='motor_vehicle_driver'
     or config.get('district')!='business'
     or config.get('duration_s')!=30 or config.get('rate_hz')!=20
     or config.get('frames')!=600 or config.get('physical_completion') is not False
     or config.get('legal_verdict') is not None):
  raise ValueError('C42387 exact scope or timing differs')
 if tuple(c.get('name') for c in config.get('cameras',()))!=VIEWS:
  raise ValueError('Four named source cameras required')
 if any(c.get('fps')!=20 or not all(c.get(k) for k in
        ('width','height','fov_deg','location_xyz_m','rotation_pyr_deg'))
        for c in config['cameras']):
  raise ValueError('Source camera geometry incomplete')
 roads=ET.fromstring(road_text).findall('road')
 if (len(roads)!=2 or roads[0].get('length')!='100' or roads[1].get('length')!='50'
     or roads[0].find('./planView/geometry/line') is None
     or roads[1].find('./planView/geometry/line') is None):
  raise ValueError('Business right-turn road proposal missing')
 if not all(config.get(k) is True for k in
       ('district_source_required','signal_state_source_required',
        'original_path_source_required','course_change_source_required')):
  raise ValueError('District, signal, path and course-change sources required')
 return {'frames':600,'source_cameras':list(VIEWS),
  'authored_right_turn':True,'original_native_observed':False,
  'carla_contacted':False,'physical_completion':False}


def measure(rows,source_kind):
 if source_kind not in ('authored_native_request','original_native'):
  raise ValueError('Unknown source kind')
 if len(rows)!=600:raise ValueError('Full 600-frame source required')
 distances=[];signals=[];turns=[]
 for i,r in enumerate(rows):
  if (r.get('frame')!=i or abs(r.get('time_s',-1)-(i+1)/20)>1e-8
      or r.get('source_kind')!=source_kind):
   raise ValueError('Frame/time/source join differs')
  d=r.get('path_length_m');s=r.get('right_signal_on')
  if (not isinstance(d,(int,float)) or d<0 or (distances and d<=distances[-1])
      or s not in (True,False) or r.get('weather')!='clear'):
   raise ValueError('Path length, signal or fixed weather source missing')
  if source_kind=='original_native' and not all(isinstance(r.get(k),dict)
    for k in ('district_review','signal_review','course_change_review')):
   raise ValueError('Original district, signal and turn source missing')
  distances.append(d);signals.append(s)
  if r.get('right_turn_begins') is True:turns.append(i)
 if turns!=[400]:raise ValueError('Single right-turn onset required')
 if not signals[399]:raise ValueError('Signal absent immediately before turn')
 first=399
 while first>0 and signals[first-1]:first-=1
 continuous_m=distances[400]-distances[first]
 return {'continuous_last_segment_m':round(continuous_m,4),
  'business_100_feet_m':FEET_100_M,
  'requested_meets_100_feet':continuous_m>=FEET_100_M,
  'original_native_observed':source_kind=='original_native','legal_verdict':None}


def read_and_measure(path,kind):
 return measure([json.loads(s) for s in Path(path).read_text().splitlines()],kind)
