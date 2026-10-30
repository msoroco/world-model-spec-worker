"""Execute each exact case's declared frame joins on proved diagnostic outputs."""
import json,hashlib
from pathlib import Path
from source_audit import join_sources
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 specs=read(ROOT/'work/_shared/source-audit-specs.json');failures=[];passed=[]
 for spec in specs:
  folder=ROOT/'work'/spec['assignment_id'];entry=next(e for e in read(folder/'execution-manifest.json')['cases'] if e['case_id']==spec['case_id']);candidates=[]
  for p in (ROOT/'.runtime-work'/spec['assignment_id']).rglob('analysis-report.json'):
   try:
    if read(p.parent/'construction.json')==read(folder/entry['construction']) and read(p)['case_id']==spec['case_id'] and sha(p.parent/'compatibility.json')==entry.get('compatibility',{}).get('sha256'):candidates.append(p.parent)
   except (OSError,ValueError):continue
  try:
   if not candidates:raise ValueError('No exact proved diagnostic output')
   attempt=max(candidates,key=lambda p:(p/'analysis-report.json').stat().st_mtime_ns)
   mapping=[json.loads(s) for s in (attempt/'video_frames.jsonl').read_text().splitlines() if s]
   sources=join_sources(attempt,spec['frame_sources'],mapping)
   passed.append({'case_id':spec['case_id'],'construction_sha256':entry['construction_sha256'],'compatibility_receipt_sha256':entry['compatibility']['sha256'],'passed':True,'scope':'Exact diagnostic frame/source joins only; full Native duration and camera/source audit remains unexecuted','joined_sources':sources})
  except Exception as e:failures.append({'case_id':spec['case_id'],'error':str(e)})
 report={'passed':not failures,'cases_passed':len(passed),'failures':failures,'cases':passed}
 (ROOT/'work/_shared/source-join-proof.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'passed':not failures,'cases_passed':len(passed),'failures':failures},indent=2))
 if failures:raise SystemExit(1)
if __name__=='__main__':main()
