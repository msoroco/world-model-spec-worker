"""Run exact-case, exact-candidate CPU offline checks for full-device drafts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT/'.runtime-work/c179824/device-full-offline'
MANIFEST = HERE/'draft-device-full-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    results = []
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT/'.runtime-work/c179824'),
               TMPDIR=str(ROOT/'.runtime-work/c179824'), PYTHONDONTWRITEBYTECODE='1')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name+'__')
        for candidate in ('primary', 'fallback1'):
            construction_sha = (entry['construction_sha256'] if candidate == 'primary'
                                else entry['candidates'][0]['construction_sha256'])
            destination = SCRATCH/suffix/candidate/construction_sha[:16]
            if destination.exists():
                recorded = destination/'offline.log'
                if not recorded.is_file():
                    raise ValueError('stale incomplete offline attempt: '+str(destination))
                output = 'prior materialization retained; original offline log verified\n'
            else:
                command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                           'offline', '--manifest', str(MANIFEST), '--case', case,
                           '--candidate', candidate, '--output', str(destination),
                           '--python', str(ROOT/'.venv-cpu/bin/python')]
                process = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                         capture_output=True)
                output = (process.stdout+'\n'+process.stderr).strip()+'\n'
                if process.returncode:
                    raise RuntimeError(case+' '+candidate+' offline failed: '+output[-1500:])
                recorded = destination/'offline.log'
            target = HERE/'draft-device-full-proofs'/suffix/(candidate+'-offline.log')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(recorded.read_text().rstrip()+'\n')
            results.append({'case_id': case, 'candidate': candidate,
                            'construction_sha256': construction_sha,
                            'offline_log': target.relative_to(HERE).as_posix(),
                            'offline_log_sha256': sha(target), 'exit_code': 0,
                            'simulation_started': False})
    receipt = HERE/'draft-device-full-offline-receipt.json'
    receipt.write_text(json.dumps({'format': 'c179824-device-full-offline-draft-v1',
                                   'cases': results, 'all_passed': True,
                                   'physical_acceptance_claimed': False}, indent=2)+'\n')
    print(json.dumps({'cases': len(results), 'all_passed': True}, sort_keys=True))


if __name__ == '__main__':
    main()
