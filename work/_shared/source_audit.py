"""Additional saved Native frame/camera integrity audit. Never replays CARLA.
Existing runtime processing owns decoding. This audit binds exact source bytes,
full planned duration, original ticks and case-specific measurement packet joins.
It does not infer rendered visibility or physical/legal acceptance.
"""
import argparse,hashlib,json,math
from pathlib import Path
NAMES=('overview','approach','reference_corner','driver_reference')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def select(value,path):
 if not path:return value
 for key in path.split('.'):value=value[int(key)] if isinstance(value,list) else value[key]
 return value

def audit(attempt,spec):
 attempt=Path(attempt);cfg=json.loads((attempt/'config.json').read_text())
 if cfg['selected_case_id']!=spec['case_id']:raise ValueError('Exact Native case differs')
 mapping=[json.loads(s) for s in (attempt/'video_frames.jsonl').read_text().splitlines() if s]
 expected=round(cfg['duration_s']*cfg['rate_hz'])
 if len(mapping)!=expected:raise ValueError('Full planned duration frame count differs')
 ids=[r['carla_frame'] for r in mapping]
 if any(r['video_frame']!=i for i,r in enumerate(mapping)) or len(set(ids))!=len(ids) or any(b!=a+1 for a,b in zip(ids,ids[1:])):raise ValueError('Original tick sequence differs')
 times={r['carla_frame']:r['time_s'] for r in mapping}
 if any(abs((b['time_s']-a['time_s'])-1/cfg['rate_hz'])>1e-4 for a,b in zip(mapping,mapping[1:])):raise ValueError('Recorded cadence differs')
 receipt=json.loads((attempt/'four-view-receipt.json').read_text())
 if receipt.get('format')!='synchronized-four-view-v1' or receipt['frames']!=expected or receipt['frame_map_sha256']!=sha(attempt/'video_frames.jsonl'):raise ValueError('Composition source map differs')
 if receipt['primary_sha256']!=sha(attempt/'raw.mkv'):raise ValueError('Primary source changed')
 for name in NAMES:
  if receipt['sources'][name]!=sha(attempt/(name+'.mkv')):raise ValueError('Original camera source changed: '+name)
 joined=join_sources(attempt,spec['frame_sources'],mapping)
 return {'format':'worker-additional-source-audit-v1','case_id':spec['case_id'],'passed':True,'recorded_only':True,'frames':expected,'joined_sources':joined,'composition_receipt_sha256':sha(attempt/'four-view-receipt.json'),'pixel_visibility_verified':False,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,'remaining_pixel_reviews':spec['pixel_review_obligations']}

def join_sources(attempt,sources,mapping):
 attempt=Path(attempt);ids=[r['carla_frame'] for r in mapping];times={r['carla_frame']:r['time_s'] for r in mapping}
 joined=[]
 for source in sources:
  path=attempt/source['path']
  value=[json.loads(s) for s in path.read_text().splitlines() if s] if path.suffix=='.jsonl' else json.loads(path.read_text())
  rows=select(value,source.get('rows_selector',''))
  if not isinstance(rows,list):rows=[rows]
  if not rows:raise ValueError('Required case-specific original frame packet is empty: '+source['path'])
  frames=[]
  for row in rows:
   frame=select(row,source['frame_key']) if source.get('frame_key') else row
   if frame not in times:raise ValueError('Case-specific measurement frame outside original recording: '+source['path'])
   frames.append(frame)
   if source.get('time_key') and abs(select(row,source['time_key'])-times[frame])>1e-4:raise ValueError('Case-specific original time differs')
  if source.get('full_recording') and frames!=ids:raise ValueError('Case-specific measurement lost original ticks')
  if source.get('full_frame_coverage') and set(frames)!=set(ids):raise ValueError('Case-specific measurement lost frame coverage')
  if source.get('frame_group_key'):
   groups={f:set() for f in ids}
   for frame,row in zip(frames,rows):groups[frame].add(select(row,source['frame_group_key']))
   if any(g!=set(source['required_groups']) for g in groups.values()):raise ValueError('Case-specific observer direction coverage incomplete')
  joined.append({'path':source['path'],'rows_selector':source.get('rows_selector',''),'rows':len(rows),'sha256':sha(path)})
 if not joined:raise ValueError('No law-specific frame sources declared')
 return joined

def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 specs=json.loads(Path(a.spec).read_text());spec=next(s for s in specs if s['case_id']==a.case)
 try:result=audit(Path(a.attempt),spec)
 except Exception as e:
  Path(a.output).write_text(json.dumps({'passed':False,'recorded_only':True,'error':str(e)},indent=2)+'\n');raise
 Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
