"""Refresh the twelve unselected source-exact offline receipts after Native edits."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
VERSION='v10'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest=ROOT/'draft-execution-manifest.json'
    cases=json.loads(manifest.read_text())['cases']
    rows=[]
    for case in cases:
        suffix=case['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            destination=ROOT/('draft-offline-'+VERSION)/suffix/candidate
            if destination.exists():raise ValueError('Retain prior offline output: '+str(destination))
            command=['python3.11',str(REPO/'runtime.py'),'offline','--manifest',str(manifest),
                     '--case',case['case_id'],'--candidate',candidate,'--output',str(destination)]
            run=subprocess.run(command,cwd=REPO,capture_output=True,text=True,timeout=300)
            log=destination/'offline.log'
            if run.returncode or not log.is_file():raise ValueError((suffix,candidate,run.stderr[-2000:]))
            rows.append({'case_suffix':suffix,'candidate_id':candidate,'exit_code':run.returncode,
                         'offline_log':str(log.relative_to(ROOT)),'offline_log_sha256':sha(log),
                         'error':None})
    summary={'format':'c104538-exact-offline-summary-'+VERSION,
             'manifest_sha256':sha(manifest),'rows':rows}
    (ROOT/'draft-offline-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return {'positive_exact_offline':len(rows),'manifest_sha256':summary['manifest_sha256']}

if __name__=='__main__':print(json.dumps(main()))
