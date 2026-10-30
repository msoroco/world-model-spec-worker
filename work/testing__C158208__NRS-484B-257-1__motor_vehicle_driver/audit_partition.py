"""CPU audit of actual saved diagnostic finalizer outputs and controlled settings."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OWNER=Path(__file__).parent
sp=importlib.util.spec_from_file_location('audit',ROOT/'work/_shared/comparison_audit.py');A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)

def main(aid):
 folder=ROOT/'work'/aid;m=json.loads((folder/'execution-manifest.json').read_text());index={}
 for e in m['cases']:
  wanted=json.loads((folder/e['construction']).read_text());candidates=[]
  for p in (ROOT/'.runtime-work'/aid).glob('**/analysis-report.json'):
   construction=p.parent/'construction.json'
   if construction.is_file() and json.loads(construction.read_text())==wanted and (p.parent/'compatibility.json').is_file() and A.sha(p.parent/'compatibility.json')==e['compatibility']['sha256'] and json.loads(p.read_text()).get('case_id')==e['case_id']:candidates.append(p)
  if not candidates:raise ValueError('No source-matching saved diagnostic report: '+e['case_id'])
  p=max(candidates,key=lambda p:p.stat().st_mtime_ns);index[e['case_id']]={'analysis_report':str(p),'config':str(p.parent/'config.json')}
 passed=[]
 for spec in json.loads((folder/'comparison-audit-specs.json').read_text()):
  result=A.audit(spec,index);path=folder/'receipts'/('comparison-'+spec['comparison_id']+'.json');path.write_text(json.dumps(result,indent=2)+'\n');passed.append({'comparison_id':spec['comparison_id'],'receipt':str(path.relative_to(folder)),'sha256':A.sha(path)})
 print(json.dumps({'assignment_id':aid,'saved_comparison_count':len(passed),'receipts':passed,'physical_comparison_complete':False},indent=2))
 return passed
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--assignment',required=True);args=p.parse_args();main(args.assignment)
