"""Verify every selected C132497 construction through the pinned offline runner."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((ROOT/'update015-current-candidate-index.json').read_text())
    rows = []
    for item in index['results']:
        case = item['case_id'].rsplit('__', 1)[-1]
        candidate = item['candidate_id']
        manifest = ROOT/item['manifest']
        if sha(manifest) != item['manifest_sha256']:
            raise ValueError('Selected manifest changed: '+case+'/'+candidate)
        output = (REPO/'.runtime-work/c132497-selected-offline'/case/candidate/
                  (item['manifest_sha256'][:12]+'-'+sha(ROOT/'native/finalize_current.py')[:12]))
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [str(REPO/'.venv-cpu/bin/python'), str(REPO/'runtime.py'),
                   'offline', '--manifest', str(manifest), '--case', item['case_id'],
                   '--candidate', candidate, '--output', str(output)]
        result = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
        log = ROOT/f'update015-selected-offline-{case}-{candidate}.log'
        log.write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError('Selected offline failed: '+str(log))
        receipt = json.loads(result.stdout)
        if (receipt.get('offline_passed') is not True or
                receipt.get('simulation_started') is not False or
                receipt.get('case_id') != item['case_id'] or
                receipt.get('candidate_id') != candidate or
                sha(output/'construction.json') != item['construction_sha256'] or
                'OK' not in (output/'offline.log').read_text()):
            raise ValueError('Selected offline receipt differs: '+case+'/'+candidate)
        rows.append({'case_id':item['case_id'], 'candidate_id':candidate,
                     'manifest_sha256':item['manifest_sha256'],
                     'construction_sha256':item['construction_sha256'],
                     'log':log.name, 'log_sha256':sha(log),
                     'runtime_log_sha256':sha(output/'offline.log'),
                     'offline_passed':True, 'simulation_started':False})
        print(json.dumps({'case':case,'candidate':candidate,'offline_passed':True}),flush=True)
    target = ROOT/'update015-selected-offline-matrix.json'
    target.write_text(json.dumps({'format':'c132497-selected-offline-v1',
        'candidate_index_sha256':sha(ROOT/'update015-current-candidate-index.json'),
        'results':rows,'original_native_observed':False},indent=2)+'\n')
    print(json.dumps({'passed':len(rows),'sha256':sha(target)}))


if __name__ == '__main__':
    main()
