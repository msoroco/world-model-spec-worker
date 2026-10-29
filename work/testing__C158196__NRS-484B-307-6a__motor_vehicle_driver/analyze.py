"""Saved-only original signal sequence and intersection-entry ordering."""
import argparse,hashlib,json
from pathlib import Path
from shapely.geometry import MultiPoint,Polygon
from worker_exchange.native_output import write_result

def required(root,name):
 p=root/name
 if not p.is_file():raise ValueError('Missing required source: '+name)
 return p

def rows(root):
 values=[json.loads(s) for s in required(root,'signal_history.jsonl').read_text().splitlines() if s]
 if not values:raise ValueError('No original signal sequence')
 return values

def control_sequence(root):
 context=json.loads(required(root,'signal_context.json').read_text());samples=rows(root)
 if not context.get('affected_lanes') or not context.get('west_signal_actor_id'):raise ValueError('Incomplete Native governing signal context')
 if any(r['signal_actor_id']!=context['west_signal_actor_id'] for r in samples):raise ValueError('Signal identity changed')
 states=[{'frame':r['frame'],'time_s':r['time_s'],'actual':r['signal_state'],'requested':r['requested_state']} for r in samples]
 return {'original_states':states,'affected_lanes':context['affected_lanes'],'vehicular_heads':context['vehicle_heads'],
  'pedestrian_heads':context['pedestrian_heads'],'roadway_route':context['route'],
  'readback_matches_requests':all(s['actual']==s['requested'] for s in states),
  'sampling_limit':'Original 20Hz API indications; emitted pixels and official status unverified'}

def entry_order(root):
 samples=rows(root);junction=Polygon([[-7,-7],[7,-7],[7,7],[-7,7]])
 entries=[];previous=False
 for r in samples:
  body=MultiPoint([(v[0],v[1]) for v in r['ego']['body_vertices_m']]).convex_hull
  overlapping=body.intersects(junction)
  if overlapping and not previous:entries.append({'frame':r['frame'],'time_s':r['time_s'],'signal_state':r['signal_state']})
  previous=overlapping
 red=[{'frame':r['frame'],'time_s':r['time_s']} for r in samples if r['signal_state']=='Red']
 yellow=[{'frame':r['frame'],'time_s':r['time_s']} for r in samples if r['signal_state']=='Yellow']
 if not yellow or not red:raise ValueError('Missing yellow-to-red original sequence')
 return {'first_yellow':yellow[0],'first_red':red[0],'body_entry_events':entries,
  'entry_observed':bool(entries),'red_at_entry_events':[v for v in entries if v['signal_state']=='Red'],
  'sample_count':len(samples),'entry_reference':'first full-body overlap with roadway-edge polygon',
  'sampling_limit':'20Hz sampled boundary crossing; legal entry interpretation remains unresolved'}

def roadway_direction(root):
 geometry=json.loads(required(root,'scenario_geometry.json').read_text())
 directed=geometry.get('directed_roadways',[])
 if not directed or not any(item.get('one_way') is True for item in directed):raise ValueError('Missing one-way roadway source')
 return {'directed_roadways':directed,'intersection_polygon':geometry['intersection_polygon'],
         'physical_verification':geometry['physical_verification']}

def finalize(root,output):
 cfg=json.loads(required(root,'config.json').read_text());sequence=control_sequence(root);entry=entry_order(root)
 specs=[('governing_yellow_red_sequence','control_sequence',sequence,['signal_context.json','signal_history.jsonl']),
        ('red_exhibition_vs_body_entry','entry_order',entry,['signal_history.jsonl']),
        ('one_way_to_two_way_route','roadway_direction',roadway_direction(root),['scenario_geometry.json'])]
 measurements={key:{'method':method,'value':value,'sources':{name:hashlib.sha256(required(root,name).read_bytes()).hexdigest() for name in names}} for key,method,value,names in specs}
 output.write_text(json.dumps({'format':'worker-analysis-report-v1','case_id':cfg['selected_case_id'],'measurements':measurements,
  'limitations':['Diagnostic three-frame sequence is a software test only.','Native signal head, governance, pixels, entry timing and full duration remain GPU checks.',
                 'Yellow itself imposes no stop duty; no legal verdict or immediacy standard is selected.']},indent=2)+'\n')
 trace=[json.loads(s) for s in required(root,'trace.jsonl').read_text().splitlines() if s]
 channels=root/'channels';channels.mkdir(exist_ok=True)
 (channels/'kin.speed.jsonl').write_text(''.join(json.dumps({'time_s':r['time_s'],'value':r['speed_mps']})+'\n' for r in trace))
 result={'case_id':cfg['selected_case_id'],'measured_values':{'first_red_frame':entry['first_red']['frame']},
  'target_checks':[{'target':'yellow_then_red_original_sequence','requested':True,'measured':entry['first_red']['frame']>entry['first_yellow']['frame'],
   'method':'original signal state readback','tolerance':0,'matched':entry['first_red']['frame']>entry['first_yellow']['frame'],
   'physical_cause_confirmed':False,'cause_evidence':'signal_history.jsonl'}],
  'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,'termination_reason':'saved analysis; Native verification pending',
  'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
  'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
  'recording_evidence':[{'name':'kin.speed','unit':'m/s','reference':'channels/kin.speed.jsonl'}],'realized_observables':{}}
 write_result(root,result)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 finalize(Path(a.attempt),Path(a.output))
