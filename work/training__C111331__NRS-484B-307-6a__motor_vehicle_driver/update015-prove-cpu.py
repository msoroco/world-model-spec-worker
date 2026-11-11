"""Run exact current offline, compatibility, and saved CPU paths for all bundles."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime.py'
MANIFEST = HERE / 'draft-execution-manifest.json'
LIBRARY = REPO / 'runtime/pipeline/library'
VALIDATOR = REPO / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
PROOFS = HERE / 'update015-proofs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    with log.open('w') as stream:
        result = subprocess.run([str(PYTHON), str(RUNTIME), *map(str, args)],
                                cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{args[0]} exit {result.returncode}: {log}\n' +
                           log.read_text()[-1500:])


def keep(source, destination):
    shutil.copyfile(source, destination)
    return {'path': destination.relative_to(HERE).as_posix(), 'sha256': sha(destination)}


def main():
    PROOFS.mkdir(exist_ok=True)
    matrix = {'format': 'c111331-update015-cpu-proof-matrix-v1',
              'scope': 'unselected synthetic diagnostic only', 'bundles': []}
    for case in ('reference', 'contrast'):
        case_id = HERE.name + '__' + case
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            label = case + '-' + candidate
            base = REPO / '.runtime-work' / ('update015-c111331-v3-' + label)
            offline, compat, processed = (Path(str(base) + '-' + suffix)
                                          for suffix in ('offline', 'compat', 'processed'))
            row = {'case_id': case_id, 'candidate_id': candidate,
                   'construction_sha256': next(
                       (entry['construction_sha256'] if candidate == 'primary' else
                        next(item['construction_sha256'] for item in entry['candidates']
                             if item['id'] == candidate))
                       for entry in json.loads(MANIFEST.read_text())['cases']
                       if entry['case_id'] == case_id)}
            try:
                run(['offline', '--manifest', MANIFEST, '--case', case_id,
                     '--candidate', candidate, '--output', offline, '--python', PYTHON],
                    PROOFS / (label + '-offline-command.log'))
                row['offline'] = keep(offline / 'offline.log', PROOFS / (label + '-offline.log'))
                run(['compatibility', '--manifest', MANIFEST, '--case', case_id,
                     '--candidate', candidate, '--output', compat,
                     '--library', LIBRARY, '--validator', VALIDATOR],
                    PROOFS / (label + '-compatibility-command.log'))
                row['compatibility'] = keep(compat / 'compatibility.json',
                                             PROOFS / (label + '-compatibility.json'))
                row['analysis_log'] = keep(compat / 'compatibility-analysis.log',
                                            PROOFS / (label + '-analysis.log'))
                row['negative_log'] = keep(compat / 'negative-analysis.log',
                                            PROOFS / (label + '-negative.log'))
                run(['process-saved', '--manifest', MANIFEST, '--case', case_id,
                     '--attempt', compat, '--output', processed,
                     '--library', LIBRARY, '--validator', VALIDATOR],
                    PROOFS / (label + '-process-command.log'))
                row['process_command'] = keep(PROOFS / (label + '-process-command.log'),
                                               PROOFS / (label + '-process.log'))
                row['passed'] = True
                print(label, 'passed', flush=True)
            except Exception as exc:
                row['passed'] = False
                row['error'] = str(exc)
                print(label, 'FAILED', str(exc)[-700:], flush=True)
            matrix['bundles'].append(row)
            (HERE / 'update015-cpu-proof-matrix.json').write_text(
                json.dumps(matrix, indent=2) + '\n')
    print('passed', sum(row['passed'] for row in matrix['bundles']), '/8', flush=True)


if __name__ == '__main__':
    main()
