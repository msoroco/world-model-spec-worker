"""Run only partition four saved exact-report comparison proofs; no Native replay."""
import json,pathlib,runpy
R=pathlib.Path(__file__).resolve().parents[2];ids=json.loads((R/'partitions/demo-test-04.json').read_text())['assignment_ids']+['testing__C24811__NRS-484B-250-4__motor_vehicle_driver','testing__C376646__NRS-484B-250-4__motor_vehicle_driver'];audit=runpy.run_path(str(R/'work/_shared/comparison_audit.py'))['audit']
for aid in ids:
 f=R/'work'/aid;m=json.loads((f/'execution-manifest.json').read_text());index={}
 for e in m['cases']:
  want=json.loads((f/e['construction']).read_text());reports=[]
  for p in (R/'.runtime-work'/aid).rglob('analysis-report.json'):
   try:
    if json.loads((p.parent/'construction.json').read_text())==want and json.loads((p.parent/'config.json').read_text())['selected_case_id']==e['case_id']:reports.append(p)
   except (OSError,ValueError):pass
  if not reports:raise ValueError('No proved source-matching exact report '+e['case_id'])
  p=max(reports,key=lambda x:x.stat().st_mtime_ns);index[e['case_id']]={'analysis_report':str(p.resolve()),'config':str((p.parent/'config.json').resolve())}
 results=[audit(s,index) for s in json.loads((f/'comparison-audit-specs.json').read_text())]
 (f/'comparison-diagnostic-index.json').write_text(json.dumps(index,indent=2)+'\n');(f/'receipts/comparison-audits.json').write_text(json.dumps(results,indent=2)+'\n');print(aid,len(results),'saved comparison proofs passed')
