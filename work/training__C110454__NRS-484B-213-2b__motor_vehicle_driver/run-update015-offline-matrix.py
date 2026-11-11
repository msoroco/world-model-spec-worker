"""Refresh all current unselected offline receipts after source reconstruction."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MANIFEST={'intersection':'draft-execution-manifest.json',
          'statutory':'draft-statutory-execution-manifest.json',
          'traversal':'draft-traversal-execution-manifest.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary=json.loads((HERE/'update015-offline-summary.json').read_text())
    rows=[]
    for row in summary['rows']:
        family=row['family'];suffix=row['case_id'].split('__')[-1]
        log=Path('update015-offline-logs-v7')/family/suffix/(row['candidate_id']+'.log')
        path=HERE/log;path.parent.mkdir(parents=True,exist_ok=True)
        output=REPO/'.runtime-work'/'c110454-update015-offline-v7'/family/suffix/row['candidate_id']
        command=[sys.executable,str(REPO/'runtime.py'),'offline','--manifest',
                 str(HERE/MANIFEST[family]),'--case',row['case_id'],
                 '--candidate',row['candidate_id'],'--output',str(output)]
        result=subprocess.run(command,cwd=REPO,capture_output=True,text=True)
        path.write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError('Current offline failed: '+str(log))
        row.update(log=log.as_posix(),log_sha256=sha(path),exit_code=0)
        rows.append(row)
        print(f'{len(rows)}/32 {family} {suffix} {row["candidate_id"]}',flush=True)
    summary['rows']=rows
    for name in summary['manifest_sha256']:
        summary['manifest_sha256'][name]=sha(HERE/name)
    (HERE/'update015-offline-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'summary_sha256':sha(HERE/'update015-offline-summary.json')}))


if __name__=='__main__':main()
