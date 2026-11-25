"""Run source-bound compatibility on all staged review-context bundles."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'review-draft-manifest.json'
VALIDATOR = REPO / '.runtime-work/c158196-current-decoder/.lake/build/bin/adapterCheck'
OUTPUT = REPO / '.runtime-work/c158196-review-compat-all'
LOGS = ROOT / 'review-draft/compatibility-proofs'
INDEX = LOGS / 'index.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(rows):
    INDEX.write_text(json.dumps({'format': 'c158196-review-draft-compatibility-proofs',
                                 'manifest_sha256': sha(MANIFEST),
                                 'validator_sha256': sha(VALIDATOR),
                                 'receipts': rows}, indent=2) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    LOGS.mkdir(parents=True, exist_ok=True)
    rows = []
    if INDEX.is_file():
        existing = json.loads(INDEX.read_text())
        if (existing.get('manifest_sha256') == sha(MANIFEST) and
                existing.get('validator_sha256') == sha(VALIDATOR)):
            rows = existing['receipts']
    proved = {(r['case_id'], r['candidate_id']) for r in rows
              if r['exit_code'] == 0 and
              (ROOT / r['log']).is_file() and
              sha(ROOT / r['log']) == r['log_sha256']}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in [{'id': 'primary', **entry}, *entry['candidates']]:
            ident = candidate['id']
            if (entry['case_id'], ident) in proved:
                continue
            destination = OUTPUT / (suffix + '-' + ident)
            log_path = LOGS / (suffix + '-' + ident + '.log')
            command = [sys.executable, str(REPO / 'runtime.py'),
                       'compatibility', '--manifest', str(MANIFEST),
                       '--case', entry['case_id'], '--output', str(destination),
                       '--library', str(REPO / 'runtime/library'),
                       '--validator', str(VALIDATOR)]
            if ident != 'primary':
                command += ['--candidate', ident]
            env = dict(os.environ,
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c158196-review-compat-all'),
                       PYTHONDONTWRITEBYTECODE='1')
            with log_path.open('w') as stream:
                result = subprocess.run(command, cwd=REPO, env=env,
                                        stdout=stream, stderr=subprocess.STDOUT,
                                        check=False)
            row = {'case_id': entry['case_id'], 'candidate_id': ident,
                   'construction_sha256': candidate['construction_sha256'],
                   'command': command, 'exit_code': result.returncode,
                   'log': str(log_path.relative_to(ROOT)),
                   'log_sha256': sha(log_path)}
            if result.returncode == 0:
                receipt = json.loads(log_path.read_text())
                if (not receipt.get('passed') or
                        receipt['construction_sha256'] != candidate['construction_sha256']):
                    raise ValueError('Compatibility proof binds another construction')
                row['negative_log_sha256'] = receipt['negative_log_sha256']
            rows.append(row)
            save(rows)
            print(suffix, ident, result.returncode, flush=True)
            if result.returncode:
                raise SystemExit('Staged compatibility proof failed')
    if len(rows) != 24:
        raise SystemExit('Staged compatibility proof incomplete')


if __name__ == '__main__':
    main()
