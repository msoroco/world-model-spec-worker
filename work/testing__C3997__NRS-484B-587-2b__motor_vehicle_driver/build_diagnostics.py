"""Produce source-hashed synthetic diagnostics with body/line crossing history."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from author_semantic import AID,HERE
from outside_lane import CASES
ROOT=HERE.parents[1]

def checksum(value):
 return sha256(value if isinstance(value,bytes) else value.encode()).hexdigest()

def encode(value):return json.dumps(value,indent=2,ensure_ascii=False)+'\n'

def run():
 base=json.loads((ROOT/'runtime/fixtures/example.json').read_text())
 assignment=ROOT/'inputs'/AID/'assignment.json';source_hash=checksum(assignment.read_bytes())
 for case in CASES:
  folder=HERE if case==CASES[0] else HERE/'cases'/case.name
  folder.mkdir(parents=True,exist_ok=True)
  generator=deepcopy(base);case_id=AID+'__'+case.name
  trace=[json.loads(line) for line in generator['files']['trace.jsonl'].splitlines()]
  frames=[json.loads(line) for line in generator['files']['video_frames.jsonl'].splitlines()]
  if len(trace)!=len(frames) or len(trace)<2:raise ValueError('structural fixture frames differ')
  synthetic={role:checksum('synthetic C3997 '+role) for role in (
   'map','marking','lane_function','designation','boundary','direction','vehicle',
   'paving','sign','emergency','authorization','camera','packet')}
  rows=[]
  for i,(motion,mapped) in enumerate(zip(trace,frames)):
   if motion['frame']!=mapped['carla_frame']:raise ValueError('structural fixture frame join differs')
   progress=i/(len(trace)-1)
   distance=(-2.0+4.0*progress) if case.origin!=case.destination else -2.0
   row={'case':case.name,'ego_id':'synthetic-ego','map_sha256':synthetic['map'],
    'lane_marking_source_sha256':synthetic['marking'],
    'lane_function_source_sha256':synthetic['lane_function'],
    'legal_controlled_access_source_sha256':synthetic['designation'],
    'public_highway_boundary_source_sha256':synthetic['boundary'],
    'direction_source_sha256':synthetic['direction'],
    'camera_plan_sha256':synthetic['camera'],
    'vehicle_class_source_sha256':synthetic['vehicle'],
    'paved_shoulder_source_sha256':synthetic['paving'],
    'lawful_shoulder_sign_source_sha256':synthetic['sign'],
    'emergency_record_source_sha256':synthetic['emergency'],
    'subsection3_authorization_source_sha256':synthetic['authorization'],
    'route_id':'synthetic-route-'+case.name,'approach':case.approach,
    'vehicle_class':case.vehicle_class,
    'origin':case.origin,'destination':case.destination,
    'separator_kind':'solid_white','separator_source_sha256':synthetic['marking'],
    'emergency_required':case.emergency_required,
    'subsection3_shoulder_authorized':case.subsection3_shoulder_authorized,
    'shoulder_paved':case.subsection3_shoulder_authorized,
    'lawful_sign_permits_shoulder':case.subsection3_shoulder_authorized,
    'original_frame':motion['frame'],'source_sha256':source_hash,
    'capture_packet_sha256':synthetic['packet'],
    'ego_speed_mps':motion['speed_mps'],'center_signed_m':distance,
    'body_min_signed_m':distance-0.6,'body_max_signed_m':distance+0.6,
    'center_segment_fraction':0.5,'body_min_segment_fraction':0.48,
    'body_max_segment_fraction':0.52}
   rows.append(row)
  history=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
  generator['files']['original-history.jsonl']=history
  capture_manifest=json.loads(generator['files']['capture/manifest.json'])
  capture_manifest['case_id']=case_id
  capture_manifest['source_run']='fixture:C3997-solid-white-'+case.name
  generator['files']['capture/manifest.json']=encode(capture_manifest)
  generator['files']['original-source-receipt.json']=encode({
   'source_kind':'synthetic_diagnostic_fixture','diagnostic_fixture':True,
   'case_id':case_id,'frame_count':len(rows),'history_sha256':checksum(history),
   'trace_sha256':checksum(generator['files']['trace.jsonl']),
   'frame_map_sha256':checksum(generator['files']['video_frames.jsonl']),
   'lane_function_source_sha256':synthetic['lane_function'],
   'source_limit':'Synthetic body positions and legal context are not original Native evidence'})
  path=folder/'fixture-generator.json';path.write_text(json.dumps(generator,separators=(',',':'),ensure_ascii=False)+'\n')
  recipe={'format':'worker-fixture-recipe',
   'sources':[{'path':'diagnostic-law-source.json','source':str(assignment.relative_to(ROOT)),
               'sha256':source_hash}],
   'generator':{'source':str(path.relative_to(ROOT)),'sha256':checksum(path.read_bytes())}}
  (folder/'fixture-recipe.json').write_text(encode(recipe))

if __name__=='__main__':run()
