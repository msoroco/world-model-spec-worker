"""Validate source bindings for a proposed signposted one-way site.

This checks completeness and byte identity only. Whether the cited designation
has legal force and whether a sign governs the route require independent review.
"""
import hashlib
import math
from pathlib import Path


def _source(root, row, label):
 if not isinstance(row,dict) or not row.get('path') or not row.get('sha256'):
  raise ValueError('Missing '+label+' source binding')
 rel=Path(row['path'])
 if rel.is_absolute() or '..' in rel.parts:
  raise ValueError('Unsafe '+label+' source path')
 path=Path(root)/rel
 if not path.is_file():raise ValueError('Missing '+label+' source file')
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=row['sha256']:raise ValueError('Stale '+label+' source hash')
 return {'path':str(rel),'sha256':digest}


def validate(packet, source_root, *, expected_map_id, road_id, lane_ids):
 if not isinstance(packet,dict):raise ValueError('Site packet must be an object')
 if packet.get('native_map_id')!=expected_map_id or packet.get('road_id')!=road_id:
  raise ValueError('Site packet Native road identity differs')
 if set(packet.get('driving_lane_ids',[]))!=set(lane_ids) or len(set(lane_ids))<2:
  raise ValueError('Site packet selected lanes differ')
 if not packet.get('highway_id') or not packet.get('designation_text'):
  raise ValueError('Designation identity and exact text required')
 direction=packet.get('designated_forward_xy')
 if not isinstance(direction,list) or len(direction)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in direction) or math.hypot(*direction)<0.5:
  raise ValueError('Designated direction invalid')
 if not packet.get('reviewer') or not packet.get('designation_review_basis'):
  raise ValueError('Independent designation review basis required')
 designation=_source(source_root,packet.get('designation_source'),'designation')
 signs=packet.get('signs')
 if not isinstance(signs,list) or not signs:
  raise ValueError('One-way sign inventory required')
 seen=set();bound=[]
 for sign in signs:
  if not isinstance(sign,dict) or not sign.get('sign_id') or sign['sign_id'] in seen:
   raise ValueError('Distinct sign identity required')
  seen.add(sign['sign_id'])
  if sign.get('code')!='one_way' or sign.get('governs_road_id')!=road_id:
   raise ValueError('Sign must be one-way and govern selected road')
  if not set(lane_ids)<=set(sign.get('governs_lane_ids',[])):
   raise ValueError('Sign coverage omits selected lane')
  location=sign.get('location_xy_m')
  if not isinstance(location,list) or len(location)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in location):
   raise ValueError('Sign location invalid')
  bound.append({'sign_id':sign['sign_id'],'source':_source(source_root,sign.get('source'),'sign')})
 return {'format':'worker-one-way-site-source-check',
         'native_map_id':expected_map_id,'highway_id':packet['highway_id'],
         'road_id':road_id,'selected_lane_ids':sorted(set(lane_ids)),
         'designation_source':designation,'sign_sources':bound,
         'legal_designation_status':'independent review required',
         'physical_sign_visibility':'unverified'}
