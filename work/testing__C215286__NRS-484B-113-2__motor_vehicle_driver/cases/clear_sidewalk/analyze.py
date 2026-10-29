"""Original body/crosswalk overlap during measured backing; no legal verdict."""
import argparse,hashlib,json,math
from pathlib import Path
from shapely.geometry import MultiPoint,box
from worker_exchange.native_output import write_result

def required(root,name):
 p=root/name
 if not p.is_file():raise ValueError('Missing required source: '+name)
 return p

def reverse_crosswalk_overlap(root):
 rows=[json.loads(s) for s in required(root,'reverse_history.jsonl').read_text().splitlines() if s]
 if not rows:raise ValueError('Missing original reverse samples')
 context=json.loads(required(root,'crosswalk_context.json').read_text());west,east,south,north=context['band_xy_m']
 stripe=box(west,south,east,north);samples=[]
 region=box(*context.get('intersection_xy_m',[-7,-7,7,7]))
 corner=context.get('corner_xy_m',[0,0])
 for row in rows:
  vertices=row['body_vertices_m']
  if len(vertices)!=8:raise ValueError('Require eight original body vertices')
  body=MultiPoint([(v[0],v[1]) for v in vertices]).convex_hull
  signed=row['velocity_mps'][0]*math.cos(math.radians(row['heading_deg']))+row['velocity_mps'][1]*math.sin(math.radians(row['heading_deg']))
  samples.append({'frame':row['frame'],'time_s':row['time_s'],'body_overlap_area_m2':body.intersection(stripe).area,
   'signed_forward_velocity_mps':signed,'reverse_control':bool(row['reverse_control']),'intersection_overlap_m2':body.intersection(region).area,'heading_deg':row['heading_deg'],'centroid_xy_m':[body.centroid.x,body.centroid.y],'corner_bearing_deg':math.degrees(math.atan2(body.centroid.y-corner[1],body.centroid.x-corner[0])),'corner_distance_m':body.centroid.distance(__import__('shapely.geometry',fromlist=['Point']).Point(*corner)),'corner_approach_gate_overlap':body.intersects(box(*context.get('corner_approach_gate_xy_m',[-8,-3,-7,3]))),'corner_departure_gate_overlap':body.intersects(box(*context.get('corner_departure_gate_xy_m',[-3,7,3,8])))})
 return {'samples':samples,'backing_overlap_original_frames':[r['frame'] for r in samples if r['reverse_control'] and r['signed_forward_velocity_mps']<0 and r['body_overlap_area_m2']>0],
  'intersection_backing_frames':[r['frame'] for r in samples if r['reverse_control'] and r['signed_forward_velocity_mps']<0 and r['intersection_overlap_m2']>0],
  'intersection_entry_transitions':[{'before_frame':a['frame'],'entry_frame':b['frame']} for a,b in zip(samples,samples[1:]) if a['intersection_overlap_m2']==0 and b['intersection_overlap_m2']>0 and b['reverse_control'] and b['signed_forward_velocity_mps']<0],
  'street_corner_progression':{'corner_xy_m':corner,'approach_gate':context.get('corner_approach_gate_xy_m',[-7,-3,-6,3]),'departure_gate':context.get('corner_departure_gate_xy_m',[-3,7,3,8]),'approach_gate_frames':[r['frame'] for r in samples if r['corner_approach_gate_overlap']],'departure_gate_frames':[r['frame'] for r in samples if r['corner_departure_gate_overlap']],'body_centroid_bearings_deg':[r['corner_bearing_deg'] for r in samples],'body_centroid_xy_m':[r['centroid_xy_m'] for r in samples],'nearest_corner_distance_m':min(r['corner_distance_m'] for r in samples),'bearing_change_deg':sum((b['corner_bearing_deg']-a['corner_bearing_deg']+180)%360-180 for a,b in zip(samples,samples[1:]))},'backing_heading_range_deg':max(r['heading_deg'] for r in samples)-min(r['heading_deg'] for r in samples),'crosswalk_definition':context.get('crosswalk_definition','marked'),'retained_region_context':context,'maximum_body_overlap_area_m2':max(r['body_overlap_area_m2'] for r in samples),'sampling_limit':'Original 20 Hz body polygon; physical stripe pixel visibility unverified'}

def crosswalk_context(root):
 value=json.loads(required(root,'crosswalk_context.json').read_text())
 if not value.get('physical_marking_source') or not value.get('band_xy_m'):raise ValueError('Incomplete crosswalk context')
 return value

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());overlap=reverse_crosswalk_overlap(root);context=crosswalk_context(root)
 values={}
 for key,method,val,name,extra in [('backing_crosswalk_body_overlap','reverse_crosswalk_overlap',overlap,'reverse_history.jsonl',['crosswalk_context.json']),
                                    ('physical_crosswalk_context','crosswalk_context',context,'crosswalk_context.json',[])]:
  values[key]={'method':method,'value':val,'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in [name,*extra]}}
 values['requirement_0']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_1']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_2']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_3']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_4']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_5']={'method':'crosswalk_context','value':crosswalk_context(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['crosswalk_context.json']}}
 values['requirement_6']={'method':'crosswalk_context','value':crosswalk_context(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['crosswalk_context.json']}}
 values['requirement_7']={'method':'crosswalk_context','value':crosswalk_context(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['crosswalk_context.json']}}
 values['requirement_8']={'method':'crosswalk_context','value':crosswalk_context(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['crosswalk_context.json']}}
 values['requirement_9']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_10']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_11']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 values['requirement_12']={'method':'reverse_crosswalk_overlap','value':reverse_crosswalk_overlap(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['reverse_history.jsonl', 'crosswalk_context.json']}}
 output.write_text(json.dumps({'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':values,
  'limitations':['Diagnostic fixture is not a physical demonstration.','Native reverse motion, full-body stripe contact and four camera pixels remain local checks.']},indent=2)+'\n')
 rows=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 (channels/'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\n' for r in rows))
 result={'case_id':cfg['selected_case_id'],'measured_values':{'maximum_crosswalk_overlap_m2':overlap['maximum_body_overlap_area_m2']},
  'target_checks':[{'target':'backing_crosswalk_body_overlap','requested':True,'measured':bool(overlap['backing_overlap_original_frames']),
    'method':'original full-body polygon and signed reverse velocity','tolerance':0,'matched':bool(overlap['backing_overlap_original_frames']),
    'physical_cause_confirmed':False,'cause_evidence':'reverse_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved diagnostic only',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
  'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'channels/kin.speed.jsonl'}],'realized_observables':{}}
 write_result(root,result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
 a=p.parse_args();finalize(Path(a.attempt),Path(a.output))
