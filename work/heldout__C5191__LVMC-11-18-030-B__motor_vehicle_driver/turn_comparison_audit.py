"""Independent source-controlled C5191 lane path and signal comparisons."""
import argparse,hashlib,json
from pathlib import Path
from turn_finalizer import measure_marked_turn

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def audit(contained,no_signal,signaled):
 roots=[Path(x) for x in (contained,no_signal,signaled)];contexts=[json.loads((p/'turn_scene_context.json').read_text()) for p in roots]
 if contexts[0]!=contexts[1] or contexts[1]!=contexts[2]:raise ValueError('C5191 fixed connected left route changed')
 for name in ('video_frames.jsonl','overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
  if len({digest(p/name) for p in roots})!=1:raise ValueError('C5191 fixed frame/camera source changed: '+name)
 traces=[rows(p/'trace.jsonl') for p in roots];originals=[rows(p/'turn_originals.jsonl') for p in roots]
 if len({len(x) for x in originals})!=1 or not originals[0]:raise ValueError('C5191 participant source length differs')
 for a,b in zip(originals[0],originals[1]):
  for k in ('frame','time_s','ego_id','original_approach_lane','ego_light_state','current_road_id','current_lane_id'):
   if a[k]!=b[k]:raise ValueError('C5191 containment fixed source changed: '+k)
 if traces[1]!=traces[2]:raise ValueError('C5191 indicator comparison trace changed')
 for a,b in zip(originals[1],originals[2]):
  for k in set(a)-{'ego_light_state'}:
   if a[k]!=b[k]:raise ValueError('C5191 indicator comparison geometry changed: '+k)
 measured=[measure_marked_turn(p) for p in roots]
 a,b,c=measured
 if not (a['minimum_approach_clearance_m']>0 and b['minimum_approach_clearance_m']<0 and c['minimum_approach_clearance_m']==b['minimum_approach_clearance_m'] and a['observed_heading_change_deg']==b['observed_heading_change_deg']==c['observed_heading_change_deg']>=45 and a['left_indicator_readback_frames']==b['left_indicator_readback_frames']==0 and c['left_indicator_readback_frames']>0):
  raise ValueError('C5191 controlled path/signal contrast missing')
 return {'format':'worker-C5191-comparison-proof','comparison_ids':['left_turn_approach_containment','left_turn_signal_evidence'],'case_ids':[json.loads((p/'config.json').read_text())['selected_case_id'] for p in roots],'fixed_route_sha256':digest(roots[0]/'turn_scene_context.json'),'fixed_camera_hashes':{n:digest(roots[0]/(n+'.mkv')) for n in ('overview','approach','reference_corner','driver_reference')},'minimum_clearances_m':[x['minimum_approach_clearance_m'] for x in measured],'indicator_frames':[x['left_indicator_readback_frames'] for x in measured],'observed_heading_change_deg':[x['observed_heading_change_deg'] for x in measured],'physical_completion_claimed':False,'legal_exception_claimed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--contained',required=True);p.add_argument('--no-signal',required=True);p.add_argument('--signaled',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=audit(a.contained,a.no_signal,a.signaled);Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'comparison_ids':r['comparison_ids'],'minimum_clearances_m':r['minimum_clearances_m'],'indicator_frames':r['indicator_frames']}))
