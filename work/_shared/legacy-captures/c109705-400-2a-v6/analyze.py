"""Exact retained v6 left-turn analysis; no capture or identity adaptation.

All motion conclusions are finite sampled engineering observations. They do not
establish a statutory nearest-position threshold, legal verdict or pixel proof.
"""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import physical_result, write_result

CASE_ID='testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__selected_left_turn'
NATIVE_SHA='f1c4c4d8443a735a4800a7ca4cd7c88db18174ec75768f86ee4551079cfcca9b'
FROZEN_SOURCES={'config.json': '79b1b7096f54e95fc0e25bb386e5e314fbb0870fb79114f7a3564082fbc5954a', 'construction.json': 'f1c4c4d8443a735a4800a7ca4cd7c88db18174ec75768f86ee4551079cfcca9b', 'road_geometry.json': '73d2feab46c84bb51adbbbbcadfe42156e1abd4d41594f5147ed7605aad67b2f', 'body_history.jsonl': '6e5170d738712807c3c964f28a13331c313e3b34ff26f8c1929f3856142ad071', 'video_frames.jsonl': 'b47f683812ff6b343026a8bdc0a8b1a1c3a877fbab0a5d9eb0a83ef1d168c6cc', 'trace.jsonl': '3b7c1cadd0c398f4165789e4964c1e3215416ed7bd776698ffe5ae9da692177e', 'capture/manifest.json': '1b6bf0238c5cb036735421fdd87b6b749800c263ca4073bf3e5c26ea47647595'}
# The frozen input is embedded below by build_package.py; no original file is rewritten.

def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def required(root,name):
 path=root/name
 if not path.is_file():raise ValueError('Missing required source: '+name)
 return path
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def validate_identity(root):
 cfg=json.loads(required(root,'config.json').read_text())
 if cfg.get('selected_case_id')!=CASE_ID or cfg.get('case',{}).get('case_id')!=CASE_ID:
  raise ValueError('Wrong retained v6 case identity; no v7 renaming is permitted')
 if json.loads(required(root,'construction.json').read_text()).get('case_id')!=CASE_ID:
  raise ValueError('Wrong retained Native construction case identity')
 if json.loads(required(root,'capture/manifest.json').read_text()).get('case_id')!=CASE_ID:
  raise ValueError('Wrong retained capture manifest case identity')
 marker=root/'acquisition-provenance.json'
 provenance=json.loads(marker.read_text()) if marker.is_file() else {}
 diagnostic=provenance.get('diagnostic_fixture') is True and provenance.get('provenance_kind')=='native'
 actual={name:sha(required(root,name)) for name in FROZEN_SOURCES}
 mismatched=[name for name,checksum in FROZEN_SOURCES.items() if actual[name]!=checksum]
 if mismatched and not diagnostic:raise RuntimeError('Frozen retained source hash differs: '+', '.join(mismatched))
 return cfg,{'exact_case_id':CASE_ID,'expected_native_construction_sha256':NATIVE_SHA,
             'source_hashes':actual,'frozen_source_hashes_match':not mismatched,
             'explicit_diagnostic_exception':diagnostic,'diagnostic_fixture':diagnostic,
             'scope':'Exact source identity; no physical or legal acceptance'}

def source_measurements(root):
 geometry=json.loads(required(root,'road_geometry.json').read_text())
 body=rows(required(root,'body_history.jsonl'));mapping=rows(required(root,'video_frames.jsonl'));trace=rows(required(root,'trace.jsonl'))
 if len(body)!=900 or len(mapping)!=900 or len(trace)!=900:raise ValueError('Retained v6 contract requires exactly900 original frames')
 samples=[];direction=geometry['approach_direction_xy'];point=geometry['approach_centerline_point_xy'];norm=math.hypot(*direction)
 if geometry.get('two_way') is not True or norm<=0:raise ValueError('Required two-directional approach geometry absent')
 for index,(b,m,t) in enumerate(zip(body,mapping,trace)):
  if b['frame']!=m['carla_frame'] or t['frame']!=m['carla_frame'] or m['video_frame']!=index:
   raise ValueError('Original v6 frame join differs')
  if abs(b['time_s']-m['time_s'])>1e-6 or abs(t['time_s']-m['time_s'])>1e-6:
   raise ValueError('Original v6 timestamp join differs')
  vertices=b['body_vertices_m']
  if len(vertices)!=8 or any(len(v)!=3 or not all(isinstance(n,(int,float)) and math.isfinite(n) for n in v) for v in vertices):
   raise ValueError('All eight finite original body vertices required')
  if b['road_id']==geometry['approach_road_id']:
   distances=[(direction[0]*(v[1]-point[1])-direction[1]*(v[0]-point[0]))/norm for v in vertices]
   samples.append({'frame':b['frame'],'time_s':b['time_s'],'signed_vertex_distances_m':distances,
                   'minimum_m':min(distances),'maximum_m':max(distances)})
 if not samples:raise ValueError('No retained original approach body samples')
 sources={n:sha(root/n) for n in ('road_geometry.json','body_history.jsonl','video_frames.jsonl','trace.jsonl')}
 return {'samples':samples,'minimum_m':min(s['minimum_m'] for s in samples),'maximum_m':max(s['maximum_m'] for s in samples),
         'original_frames':len(body),'scope':'Original v6 full-body signed offsets; no lawful lateral cutoff'},sources,body,trace

def finalize(root,output):
 root=Path(root);cfg,identity=validate_identity(root)
 motion,sources,body,trace=source_measurements(root)
 channels=root/'channels';channels.mkdir(exist_ok=True)
 for name,values in [('kin.speed',[r['speed_mps'] for r in trace]),('kin.velocity',[r['velocity_mps'] for r in trace]),('body_vertices',[r['body_vertices_m'] for r in body])]:
  (channels/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':v})+'\n' for r,v in zip(trace,values)))
 maximum=max(r['speed_mps'] for r in trace)
 target=cfg['requested_speed_mps']
 result={'case_id':CASE_ID,'measured_values':{'offset_min_m':motion['minimum_m'],'offset_max_m':motion['maximum_m'],'max_sampled_speed_mps':maximum},
  'target_checks':[{'target':'requested_speed_mps','requested':target,'measured':maximum,'method':'Maximum original900-frame velocity sample; engineering controller tolerance only','tolerance':1.0,'matched':abs(maximum-target)<=1.0,'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],
  'termination_reason':'Saved retained v6 motion assessment; no legal verdict',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
  'recording_evidence':[{'name':n,'unit':u,'reference':'channels/'+n+'.jsonl'} for n,u in [('kin.speed','m/s'),('kin.velocity','m/s'),('body_vertices','structured record')]]}
 result=physical_result(root,result)
 # Exact frozen source fingerprints bind the real historical acquisition even if
 # its older format has no new seal/provenance marker. Diagnostic exceptions
 # remain explicit and can never establish actual recording acceptance.
 if identity['frozen_source_hashes_match']:
  result['provenance_kind']='native';result['diagnostic_fixture']=False
 result['legacy_source_identity']=identity
 write_result(root,result)
 report={'format':'worker-analysis-report-v1','case_id':CASE_ID,
  'measurements':{'approach_full_body_centerline_offsets':{'method':'source_measurements','value':motion,'sources':sources}},
  'physical_checks':result['physical_checks'],'realized_observables':result['realized_observables'],
  'provenance_kind':result['provenance_kind'],'diagnostic_fixture':result['diagnostic_fixture'],'legacy_source_identity':identity,
  'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
  'limitations':['Finite20Hz original samples do not establish between-frame behavior or a continuous statutory nearest portion.',
                 'Original pixels, actual public-way/driver provenance and unresolved legal judgments require independent operator review.',
                 'Explicit synthetic Native-style diagnostics exercise software only and are never accepted recordings.']}
 Path(output).write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);args=p.parse_args();finalize(Path(args.attempt),Path(args.output))
