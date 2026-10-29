"""Original body-vertex centerline measurements, without legal position threshold."""
import argparse,hashlib,json,math
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root,name):
 path=root/name
 if not path.is_file():raise ValueError('Missing required source: '+name)
 return path

def signed_offsets(direction,point,vertices):
 dx,dy=direction;norm=math.hypot(dx,dy)
 if norm<=0 or len(vertices)<4:raise ValueError('Directed road and complete body vertices required')
 return [(dx*(v[1]-point[1])-dy*(v[0]-point[0]))/norm for v in vertices]

def measured_approach(root):
 road=json.loads(required(root,'road_geometry.json').read_text());rows=[json.loads(s) for s in required(root,'body_history.jsonl').read_text().splitlines() if s]
 if not road.get('two_way'):raise ValueError('Selected branch lacks two-way road source')
 samples=[]
 for row in rows:
  if row['road_id']!=road['approach_road_id']:continue
  values=signed_offsets(road['approach_direction_xy'],road['approach_centerline_point_xy'],row['body_vertices_m'])
  samples.append({'frame':row['frame'],'time_s':row['time_s'],'signed_vertex_distances_m':values,'minimum_m':min(values),'maximum_m':max(values)})
 if not samples:raise ValueError('No original approach body samples')
 return {'samples':samples,'minimum_m':min(s['minimum_m'] for s in samples),'maximum_m':max(s['maximum_m'] for s in samples),
  'road_direction_xy':road['approach_direction_xy'],'scope':'all body vertices in every recorded approach sample; no statutory nearest cutoff'}

def measured_departure(root):
 road=json.loads(required(root,'road_geometry.json').read_text());rows=[json.loads(s) for s in required(root,'body_history.jsonl').read_text().splitlines() if s]
 if not road.get('two_way'):raise ValueError('Selected branch lacks two-way road source')
 samples=[]
 for row in rows:
  if row['road_id']!=road['departure_road_id']:continue
  values=signed_offsets(road['departure_direction_xy'],road['departure_centerline_point_xy'],row['body_vertices_m'])
  samples.append({'frame':row['frame'],'time_s':row['time_s'],'signed_vertex_distances_m':values,'minimum_m':min(values),'maximum_m':max(values)})
 if not samples:raise ValueError('No original departure body samples')
 return {'samples':samples,'minimum_m':min(s['minimum_m'] for s in samples),'maximum_m':max(s['maximum_m'] for s in samples),
  'road_direction_xy':road['departure_direction_xy'],'scope':'all body vertices in every recorded departure sample; no legal verdict'}

def two_way_context(root):
 road=json.loads(required(root,'road_geometry.json').read_text())
 return {'two_way':bool(road['two_way']),'approach_road_id':road['approach_road_id'],'departure_road_id':road['departure_road_id'],
  'connector_road_id':road['connector_road_id'],'public_highway_designation':road['public_highway_designation'],
  'route_waypoint_count':len(road.get('route_waypoints_native_xy',[]))}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());mode=cfg['measurement_mode']
 if mode=='approach':measure=measured_approach(root);method='measured_approach';key='approach_full_body_centerline_offsets'
 else:measure=measured_departure(root);method='measured_departure';key='departure_full_body_centerline_offsets'
 sha=lambda name:hashlib.sha256(required(root,name).read_bytes()).hexdigest()
 context=two_way_context(root)
 report={'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':{
  key:{'method':method,'value':measure,'sources':{'road_geometry.json':sha('road_geometry.json'),'body_history.jsonl':sha('body_history.jsonl')}},
  'two_way_road_context':{'method':'two_way_context','value':context,'sources':{'road_geometry.json':sha('road_geometry.json')}}},
  'limitations':['Diagnostic fixture is synthetic software data, not actual CARLA evidence.',
   'Native road-direction readback, full-body trajectory, original pixels and public-way status require local GPU/source review.',
   'No numeric definition of nearest portion or legal compliance is asserted.']}
 output.write_text(json.dumps(report,indent=2)+'\n')
 rows=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 body=[json.loads(s) for s in required(root,'body_history.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 for name,values in [('kin.speed',[r['speed_mps'] for r in rows]),('kin.velocity',[r['velocity_mps'] for r in rows])]:
  (channels/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':v})+'\n' for r,v in zip(rows,values)))
 (channels/'body_vertices.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['body_vertices_m']})+'\n' for r in body))
 case=cfg['case'];result={'case_id':case['case_id'],'measured_values':{'offset_min_m':measure['minimum_m'],'offset_max_m':measure['maximum_m']},
  'target_checks':[{'target':'full_body_centerline_samples','requested':cfg['measurement_mode'],'measured':len(measure['samples']),
   'method':method,'tolerance':0,'matched':len(measure['samples'])>0,'physical_cause_confirmed':False,'cause_evidence':'body_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved analysis; native physical checks pending',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],
  'recording_evidence':[{'name':name,'unit':unit,'reference':path} for name,unit,path in [('kin.speed','m/s','channels/kin.speed.jsonl'),
   ('kin.velocity','m/s','channels/kin.velocity.jsonl'),('body_vertices','structured record','channels/body_vertices.jsonl')]],'realized_observables':{}}
 write_result(root,result);return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 finalize(Path(a.attempt),Path(a.output))
