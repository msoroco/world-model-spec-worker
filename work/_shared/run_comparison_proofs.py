"""Run declared comparison audits against case-specific diagnostic reports."""
import json,hashlib,sys
from pathlib import Path
from comparison_audit import audit
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 results=[]
 for source in sorted((ROOT/'work').glob('*/comparison-audit-specs.json')):
  specs=read(source)
  if isinstance(specs,dict):specs=specs.get('comparisons',specs.get('specs',[]))
  folder=source.parent;m=read(folder/'execution-manifest.json');index={}
  for e in m['cases']:
   expected=read(folder/e['construction'])
   key=hashlib.sha256((e['case_id']+'|primary').encode()).hexdigest()[:16]
   report=ROOT/'.runtime-work/v7-case-proofs'/key/'compat/analysis-report.json'
   try:
    cfg=read(report.parent/'config.json');construction=read(report.parent/'construction.json')
    if not (cfg.get('selected_case_id')==e['case_id'] and construction==expected
            and read(report).get('case_id')==e['case_id']
            and hashlib.sha256((report.parent/'compatibility.json').read_bytes()).hexdigest()==e.get('compatibility',{}).get('sha256')):
     raise ValueError('Current exact diagnostic provenance differs')
   except (OSError,ValueError) as error:
    raise ValueError('No proved exact v7 diagnostic analysis for '+e['case_id']) from error
   index[e['case_id']]={'analysis_report':str(report),'config':str(report.parent/'config.json')}
  write(folder/'comparison-diagnostic-index.json',index)
  declared={c['comparison_id'] for c in read(folder/'case-plan.json')['comparisons']}
  if {s['comparison_id'] for s in specs}!=declared:raise ValueError('Comparison audit coverage differs for '+folder.name)
  proofs=[]
  for spec in specs:
   result=audit(spec,index);result['scope']='Diagnostic software comparison; Native and pixel acceptance remain unverified';proofs.append(result)
  write(folder/'receipts/comparison-audits.json',proofs)
  results.append({'assignment_id':folder.name,'comparisons':len(proofs),'passed':True,'spec_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
 write(ROOT/'work/_shared/comparison-proofs.json',results)
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()
