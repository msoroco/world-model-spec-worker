"""Independent CPU diagnostics for selected C110741 delivery intent.

No synthetic fixture can certify actual pixels, CARLA motion, or local acceptance.
"""
import argparse,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
NAMES=('overview','approach','reference_corner','driver_reference')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def overlap(body,crosswalk):
 x=[p[0] for p in body];y=[p[1] for p in body];cx=[p[0] for p in crosswalk];cy=[p[1] for p in crosswalk]
 return max(0,min(max(x),max(cx))-max(min(x),min(cx)))*max(0,min(max(y),max(cy))-max(min(y),min(cy)))
def context(case):
 manifest=read(HERE/'execution-manifest.json')
 entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
 if entry is None:raise ValueError('Unknown selected case')
 s=case.split('__')[-1];letter=s[-1]
 return entry,s,letter
def delivery(case,negative):
 e,s,l=context(case)
 root=(HERE/'physical-fixtures'/s if negative else HERE/'diagnostic-sources'/s); rows_path=root/'native_samples.jsonl'
 if not rows_path.is_file():raise ValueError('Missing required source: native_samples.jsonl')
 rows=[json.loads(line) for line in rows_path.read_text().splitlines()]
 if len(rows)!=480 or [r['native_frame'] for r in rows]!=list(range(100,580)):
  raise ValueError('Native frame continuity differs')
 recipe=read(HERE/f'diagnostic-{s}-recipe.json')
 source={item['path']:item for item in recipe['sources']}
 for name in ('native_samples.jsonl','video_frames.jsonl','road_geometry.json','trace.jsonl','capture/evidence.jsonl'):
  item=source.get(name)
  if item is None or sha(HERE.parent.parent/item['source'])!=item['sha256']:raise ValueError('Retained source hash differs: '+name)
 proof=read(HERE/f'v2-proof-{l}-primary.json');report=read(HERE/f'v2-report-{l}-primary.json');decode=read(HERE/f'v2-decode-{l}-primary.json')
 if proof.get('construction_sha256')!=e['construction_sha256'] or proof.get('case_id')!=case or proof.get('passed') is not True:raise ValueError('Selected compatibility differs')
 if proof['fixture_manifest']['native_samples.jsonl']!=sha(rows_path):raise ValueError('Native source differs from compatibility receipt')
 if {name+'.mkv' for name in NAMES}-set(proof['fixture_manifest']):raise ValueError('Four source cameras missing')
 if decode.get('passed') is not True or decode.get('frames')!=480:raise ValueError('Full video decode missing')
 if report['original_joins']['frames']!=480 or report['case_id']!=case:raise ValueError('Original trace join differs')
 areas=[overlap(r['body_xy_m'],r['crosswalk_polygon_xy_m']) for r in rows if r['signed_forward_velocity_m_s']<-.05]
 area=max(areas,default=0)
 if abs(area-report['measurements']['crosswalk_overlap_area_m2']['value'])>1e-6:raise ValueError('Independent body overlap differs')
 return {'passed':True,'case_id':case,'source_frames':len(rows),'backing_frames':len(areas),'max_crosswalk_overlap_m2':area,'four_camera_sources':True,'full_decode':True,'scope':'synthetic CPU diagnostic; actual pixels/physical completion unverified','accepted':False}
def comparison(reject_drift=False):
 manifest=read(HERE/'execution-manifest.json'); e={x['case_id'].split('__')[-1]:x for x in manifest['cases']}
 if set(e)!={'condition_a','condition_b'}:raise ValueError('Comparison cases differ')
 results={s:delivery(v['case_id'],False) for s,v in e.items()}
 fixed=('cell_id','law_id','actor','duration_s','rate_hz','required_atoms','source_packets','mandatory_channels','recording_description','cameras','engineering_knobs')
 for candidate in ('primary','fallback1','fallback2','fallback3'):
  configs=[]
  for s in ('condition_a','condition_b'):
   entry=e[s];ref=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
   path=HERE/ref['construction']
   if sha(path)!=ref['construction_sha256']:raise ValueError('Selected construction hash changed')
   c=read(path);config=json.loads(next(f['content'] for f in c['files'] if f['path']=='config.json'))
   configs.append(config)
  if reject_drift and candidate=='primary':configs[1]['duration_s']=25
  if any(configs[0][key]!=configs[1][key] for key in fixed):raise ValueError('Comparison fixed condition changed: '+candidate)
 a,b=results['condition_a']['max_crosswalk_overlap_m2'],results['condition_b']['max_crosswalk_overlap_m2']
 if a!=0 or not 3<b<4:raise ValueError('Declared path-overlap difference missing')
 return {'passed':True,'fixed_condition_candidates':4,'max_overlap_m2':{'condition_a':a,'condition_b':b},'scope':'synthetic controlled comparison only'}
def triggers():
 manifest=read(HERE/'execution-manifest.json'); seen=[]
 for entry in manifest['cases']:
  for c in entry['candidates']:
   t=c['trigger'];value=float(t['threshold']);op=t['op']
   if not t['source'] or not t['metric'] or not t['failure_condition'] or not c['changed_knobs']:raise ValueError('Incomplete physical trigger')
   test=lambda x:x>value if op=='>' else x<value if op=='<' else None
   if test(value) or not test(value+(.01 if op=='>' else -.01)) or test(value+(-.01 if op=='>' else .01)):
    raise ValueError('Trigger boundary changed')
   seen.append((entry['case_id'],c['id'],t['metric']))
 if len(seen)!=6 or any(len({m for _,_,m in seen if _case==case})!=3 for case in {x[0] for x in seen} for _case in [case]):
  raise ValueError('Candidate triggers not distinct')
 return {'passed':True,'tested_trigger_boundaries':len(seen),'scope':'predeclared engineering decisions, not observed physical failures'}
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('delivery','comparison','triggers'));p.add_argument('--case');p.add_argument('--reject-missing-source',action='store_true');p.add_argument('--reject-comparison-drift',action='store_true');a=p.parse_args()
 if a.mode=='delivery' and not a.case:p.error('--case required')
 result=delivery(a.case,a.reject_missing_source) if a.mode=='delivery' else comparison(a.reject_comparison_drift) if a.mode=='comparison' else triggers()
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
