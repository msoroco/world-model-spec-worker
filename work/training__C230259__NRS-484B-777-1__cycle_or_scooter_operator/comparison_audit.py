"""Independent source-bound right-edge/standing-vehicle paired audit."""
import argparse,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def one(root,case):
 root=Path(root)
 config=json.loads((root/'config.json').read_text())
 context=json.loads((root/'context.json').read_text())
 report=json.loads((root/'analysis-report.json').read_text())
 tracks=[json.loads(s) for s in (root/'native-cycle-frames.jsonl').read_text().splitlines()]
 if config['case_id']!=case or len(tracks)!=600 or any(t['frame']!=i for i,t in enumerate(tracks)):
  raise ValueError('Incomplete or wrong exact comparison source')
 if any(t['source_kind']!='synthetic_native_sample' for t in tracks):
  raise ValueError('Comparison provenance changed')
 if report.get('legal_verdict') is not None or context.get('legal_verdict') is not None:
  raise ValueError('Comparison cannot assign legal outcome')
 scope=report['right_edge_scope']
 return {'case_id':case,'requested_center_y_m':config['requested_cycle_center_y_m'],
  'observed_right_edge_body_margin_min_m':scope['right_edge_body_margin_min_m'],
  'observed_standing_clearance_min_m':scope['standing_vehicle_clearance_min_m'],
  'standing_pass_frames':len(scope['standing_vehicle_pass_frames']),
  'fixed_conditions_id':context['fixed_conditions_id'],'source_kind':context['source_kind'],
  'source_hashes':{n:sha(root/n) for n in ('config.json','context.json','native-cycle-frames.jsonl',
    'native-map-readback.json','standing-vehicle.json','analysis-report.json')}}
def audit(ra,rb,ca,cb,comparison):
 a,b=one(ra,ca),one(rb,cb)
 if a['fixed_conditions_id']!=b['fixed_conditions_id'] or a['source_kind']!=b['source_kind']:
  raise ValueError('Comparison fixed conditions differ')
 if not a['requested_center_y_m']<b['requested_center_y_m'] or not a['observed_right_edge_body_margin_min_m']<b['observed_right_edge_body_margin_min_m']:
  raise ValueError('Selected measured right-edge contrast absent')
 return {'format':'c230259-independent-comparison-audit-v1','comparison_id':comparison,
  'cases':[a,b],'deliberate_difference':'cycle_lateral_distance_from_right_edge',
  'observed_margin_delta_m':round(b['observed_right_edge_body_margin_min_m']-a['observed_right_edge_body_margin_min_m'],5),
  'diagnostic_fixture':True,'physical_acceptance':False,'legal_verdict':None,
  'limitations':['Measured margins and clearances do not decide practicability, due care or statutory safety exceptions.']}
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ('root-a','root-b','case-a','case-b','comparison','output'):p.add_argument('--'+name,required=True)
 a=p.parse_args(); result=audit(a.root_a,a.root_b,a.case_a,a.case_b,a.comparison)
 Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'comparison_id':a.comparison,'observed_margin_delta_m':result['observed_margin_delta_m'],
  'physical_acceptance':False}))
