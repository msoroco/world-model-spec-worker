"""Audit saved controlled comparisons without replay or legal acceptance.
Specs declare exact report selectors and fixed configuration selectors. Input index
maps each exact case to its saved analysis report and materialized config. Pixel
review remains separate and is never inferred from diagnostic measurements.
"""
import argparse,hashlib,json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def select(value,path):
 for key in path.split('.'):
  value=value[int(key)] if isinstance(value,list) else value[key]
 return value

def audit(spec,index):
 if len(spec['case_ids'])<2:raise ValueError('Comparison needs at least two exact cases')
 cases={}
 for cid in spec['case_ids']:
  item=index[cid];report_path=Path(item['analysis_report']);config_path=Path(item['config'])
  report=json.loads(report_path.read_text());config=json.loads(config_path.read_text())
  if report.get('case_id')!=cid or config.get('selected_case_id')!=cid:raise ValueError('Exact case identity differs')
  for measurement in report.get('measurements',{}).values():
   for source,checksum in measurement.get('sources',{}).items():
    path=(report_path.parent/source).resolve()
    if report_path.parent.resolve() not in path.parents or sha(path)!=checksum:raise ValueError('Measured acquisition source changed: '+source)
  cases[cid]={'report':report,'config':config,'hashes':{'analysis_report':sha(report_path),'config':sha(config_path)}}
 for key in spec['fixed_config_selectors']:
  values=[select(v['config'],key) for v in cases.values()]
  if any(v!=values[0] for v in values[1:]):raise ValueError('Controlled comparison changed fixed configuration: '+key)
 checks=[]
 for check in spec['checks']:
  values=[select(cases[c]['report'],check['selector']) for c in check['case_ids']]
  op=check['operator']
  if op=='strictly_increasing':passed=all(a<b for a,b in zip(values,values[1:]))
  elif op=='equal':passed=all(v==values[0] for v in values[1:])
  elif op=='distinct':passed=any(v!=values[0] for v in values[1:])
  elif op=='expected':passed=values==check['expected_values']
  else:raise ValueError('Unsupported measured comparison operator: '+op)
  if not passed:raise ValueError('Measured comparison failed: '+check['name'])
  checks.append({'name':check['name'],'values':values,'passed':True})
 if not checks:raise ValueError('No measured comparison checks')
 return {'format':'worker-saved-comparison-audit-v1','comparison_id':spec['comparison_id'],'passed':True,'checks':checks,'source_hashes':{cid:v['hashes'] for cid,v in cases.items()},'native_replay_requested':False,'legal_acceptance_claimed':False,'pixel_acceptance_claimed':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--index',required=True);p.add_argument('--output',required=True);p.add_argument('--comparison');a=p.parse_args()
 spec=json.loads(Path(a.spec).read_text());index=json.loads(Path(a.index).read_text())
 if isinstance(spec,dict) and 'comparisons' in spec:spec=spec['comparisons']
 if isinstance(spec,list):
  matches=[s for s in spec if s['comparison_id']==a.comparison]
  if len(matches)!=1:raise ValueError('Select one exact comparison with --comparison')
  spec=matches[0]
 try:result=audit(spec,index)
 except Exception as e:
  Path(a.output).write_text(json.dumps({'passed':False,'error':str(e),'native_replay_requested':False},indent=2)+'\n');raise
 Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
