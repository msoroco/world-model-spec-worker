"""Current-input exact construction, source compatibility, and saved CPU proof."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
PROOFS = HERE / 'update043-selected-proofs'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise RuntimeError(f'{command[1]} exit {result.returncode}: {log}\n' +
                           log.read_text()[-1800:])


def copy(source, target):
    shutil.copyfile(source, target)
    return {'path': target.relative_to(HERE).as_posix(), 'sha256': sha(target)}


def main():
    if not VALIDATOR.is_file():
        raise ValueError('Pinned Lean validator missing')
    manifest = json.loads(MANIFEST.read_text())
    PROOFS.mkdir(exist_ok=True)
    matrix = {'format': 'c111331-selected-current-cpu-proof-v1',
              'diagnostic_only': True, 'rows': []}
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        for candidate in (entry, *entry['candidates']):
            name = candidate['id']
            target = PROOFS / suffix / name
            target.mkdir(parents=True, exist_ok=True)
            base = ROOT / '.runtime-work' / f'c111331-update043b-{suffix}-{name}'
            offline = Path(str(base) + '-offline')
            compat = Path(str(base) + '-compat')
            processed = Path(str(base) + '-processed')
            construction = HERE / candidate['construction']
            if sha(construction) != candidate['construction_sha256']:
                raise ValueError('Selected construction hash differs')
            row = {'case_id': case, 'candidate_id': name,
                   'construction_sha256': candidate['construction_sha256']}
            try:
                python = str(sys.executable)
                offline_cmd = [python, str(ROOT / 'runtime.py'), 'offline',
                               '--manifest', str(MANIFEST), '--case', case,
                               '--candidate', name, '--output', str(offline),
                               '--python', python]
                run(offline_cmd, target / 'run-offline.log')
                row['offline'] = copy(offline / 'offline.log', target / 'offline.log')
                candidate['offline'] = {'command': ' '.join(offline_cmd),
                    'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                    'log': str((target / 'run-offline.log').relative_to(HERE)),
                    'log_sha256': sha(target / 'run-offline.log')}
                compat_cmd = [python, str(ROOT / 'runtime.py'), 'compatibility',
                              '--manifest', str(MANIFEST), '--case', case,
                              '--candidate', name, '--output', str(compat),
                              '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
                run(compat_cmd, target / 'run-compat.log')
                row['compatibility'] = copy(compat / 'compatibility.json', target / 'compatibility.json')
                row['analysis'] = copy(compat / 'compatibility-analysis.log', target / 'analysis.log')
                row['negative'] = copy(compat / 'negative-analysis.log', target / 'negative.log')
                receipt = json.loads((target / 'compatibility.json').read_text())
                if not receipt['passed'] or receipt['construction_sha256'] != candidate['construction_sha256']:
                    raise ValueError('Compatibility receipt does not bind selected construction')
                candidate['compatibility'] = {
                    'receipt': row['compatibility']['path'], 'sha256': row['compatibility']['sha256'],
                    'log': row['analysis']['path'], 'negative_log': row['negative']['path']}
                saved_cmd = [python, str(ROOT / 'runtime.py'), 'process-saved',
                             '--manifest', str(MANIFEST), '--case', case,
                             '--attempt', str(compat), '--output', str(processed),
                             '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
                run(saved_cmd, target / 'process-command.log')
                row['saved_process'] = {'command': ' '.join(saved_cmd),
                    'log': str((target / 'process-command.log').relative_to(HERE)),
                    'log_sha256': sha(target / 'process-command.log')}
                row['passed'] = True
                print(suffix, name, 'passed', flush=True)
            except Exception as exc:
                row['passed'] = False
                row['error'] = str(exc)
                print(suffix, name, 'FAILED', str(exc)[-1000:], flush=True)
            matrix['rows'].append(row)
            (HERE / 'update043-selected-proof-matrix.json').write_text(json.dumps(matrix, indent=2) + '\n')
            MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    if not all(row['passed'] for row in matrix['rows']):
        raise RuntimeError('One or more selected CPU chains failed')
    print(json.dumps({'passed': len(matrix['rows']), 'matrix_sha256': sha(HERE / 'update043-selected-proof-matrix.json')}))


if __name__ == '__main__':
    main()
