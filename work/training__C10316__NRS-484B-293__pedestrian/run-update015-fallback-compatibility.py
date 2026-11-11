"""Run current strict compatibility for six unselected C10316 fallback bundles."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'draft-execution-manifest.json'
VALIDATOR=ROOT/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Build current decoder before fallback diagnostics')
    rows=[]
    for suffix in ('reference','contrast'):
        case=HERE.name+'__'+suffix
        for candidate in ('fallback1','fallback2','fallback3'):
            output=ROOT/'.runtime-work'/('c10316-v15-'+suffix+'-compat-'+candidate)
            log=HERE/('update015-'+suffix+'-compat-'+candidate+'.log')
            command=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'compatibility',
                     '--manifest',str(MANIFEST),'--case',case,'--candidate',candidate,
                     '--output',str(output),'--library',str(ROOT/'runtime/pipeline/library'),
                     '--validator',str(VALIDATOR)]
            with log.open('w') as stream:
                completed=subprocess.run(command,cwd=ROOT,stdout=stream,
                                         stderr=subprocess.STDOUT,timeout=600)
            row={'case_id':case,'candidate_id':candidate,'command':' '.join(command),
                 'exit_code':completed.returncode,'log':log.relative_to(HERE).as_posix(),
                 'log_sha256':sha(log)}
            receipt=output/'compatibility.json'
            if receipt.is_file():
                proof=json.loads(receipt.read_text())
                row.update(receipt_sha256=sha(receipt),
                           construction_sha256=proof['construction_sha256'],
                           passed=proof['passed'],
                           checks=proof['checks'])
            rows.append(row)
            print(suffix,candidate,completed.returncode,flush=True)
    summary={'format':'c10316-current-fallback-compatibility',
             'runtime_manifest_sha256':json.loads(MANIFEST.read_text())['runtime_manifest_sha256'],
             'manifest_sha256':sha(MANIFEST),'results':rows,
             'scope':'synthetic diagnostic compatibility; no Native or legal acceptance'}
    (HERE/'update015-fallback-compatibility-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if any(row['exit_code'] or not row.get('passed') for row in rows):
        raise SystemExit(1)


if __name__=='__main__':main()
