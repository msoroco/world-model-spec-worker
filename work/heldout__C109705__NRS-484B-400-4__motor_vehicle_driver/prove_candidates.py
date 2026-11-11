"""Offline and positive/negative compatibility proofs for every turn candidate."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'probe-compatibility-manifest.json'
PYTHON = str(REPO / '.venv-cpu/bin/python')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = json.loads(MANIFEST.read_text())['cases']
    records = []
    for entry in entries:
        case = entry['case_id']
        slug = case.split('__')[-1]
        for candidate in ['primary'] + [item['id'] for item in entry['candidates']]:
            row = {'case_id': case, 'candidate_id': candidate}
            for mode, extras in (
                    ('offline', ['--python', PYTHON]),
                    ('compatibility', ['--library', str(REPO / 'runtime/library'),
                                       '--validator', str(REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck')])):
                stem = REPO / ('.runtime-work/c109705-candidate-' + slug + '-' + candidate + '-' + mode)
                revision = 1
                output = Path(f'{stem}-v{revision}')
                while output.exists():
                    revision += 1
                    output = Path(f'{stem}-v{revision}')
                command = [PYTHON, str(REPO / 'runtime.py'), mode,
                           '--manifest', str(MANIFEST), '--case', case,
                           '--candidate', candidate, '--output', str(output)] + extras
                process = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
                log = ROOT / 'cases' / ('proof-' + slug + '-' + candidate + '-' + mode + '.log')
                log.write_text(process.stdout + process.stderr)
                if process.returncode:
                    raise ValueError(f'{slug} {candidate} {mode} failed: {process.stdout[-400:]} {process.stderr[-1400:]}')
                receipt = json.loads(process.stdout)
                if mode == 'offline' and not receipt.get('offline_passed'):
                    raise ValueError('Offline receipt did not pass')
                if mode == 'compatibility' and (not receipt.get('passed')
                                                or 'negative_case_source' not in receipt.get('checks', [])):
                    raise ValueError('Positive/negative compatibility receipt did not pass')
                row[mode + '_log'] = str(log.relative_to(ROOT))
                row[mode + '_log_sha256'] = sha(log)
                row[mode + '_receipt'] = receipt
            records.append(row)
            print(slug, candidate, 'offline and positive/negative compatibility passed', flush=True)
    (ROOT / 'candidate-proofs.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
