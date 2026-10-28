"""Rerun every frozen case's offline and package compatibility CPU gates."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / '.venv-cpu/bin/python'
VALIDATOR = ROOT / '.runtime-work/decoder005/.lake/build/bin/adapterCheck'
LIBRARY = ROOT / 'runtime/main-pipeline-v1/library'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, log):
    with log.open('x') as stream:
        completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT, text=True)
    return {'command': command, 'exit_code': completed.returncode, 'log': str(log.relative_to(ROOT)),
            'sha256': sha(log)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', required=True, help='Fresh directory name under .runtime-work')
    args = parser.parse_args()
    output = ROOT / '.runtime-work' / args.prefix
    output.mkdir(parents=True, exist_ok=False)
    logs = ROOT / 'work/_shared/lead-logs005'
    logs.mkdir(parents=True, exist_ok=True)
    batch = json.loads((ROOT / 'batch.json').read_text())
    cases = []
    for assignment_id in batch['assignments']:
        folder = ROOT / 'work' / assignment_id
        manifest = folder / 'execution-manifest.json'
        for entry in json.loads(manifest.read_text())['cases']:
            case_id = entry['case_id']
            fixture_name = entry.get('compatibility', {}).get('fixture',
                         str((folder / 'fixture-diagnostic').relative_to(ROOT)))
            fixture = ROOT / fixture_name
            case_output = output / case_id
            case_output.mkdir()
            offline = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(manifest), '--case', case_id,
                       '--output', str(case_output / 'offline')]
            compatibility = [str(PYTHON), str(ROOT / 'runtime.py'), 'compatibility',
                             '--manifest', str(manifest), '--case', case_id,
                             '--fixture', str(fixture), '--output', str(case_output / 'compatibility'),
                             '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
            record = {'assignment_id': assignment_id, 'case_id': case_id,
                      'offline': execute(offline, logs / (case_id + '.offline.log')),
                      'compatibility': execute(compatibility, logs / (case_id + '.compatibility.log'))}
            receipt = case_output / 'compatibility/compatibility.json'
            if receipt.is_file():
                record['compatibility_receipt_sha256'] = sha(receipt)
            analysis_log = case_output / 'compatibility/compatibility-analysis.log'
            if analysis_log.is_file():
                record['compatibility_analysis_log_sha256'] = sha(analysis_log)
            cases.append(record)
            print(f'{len(cases)} {case_id}', flush=True)
    report = {'format': 'lead-update005-validation-v1', 'cases': cases,
              'all_offline_passed': all(c['offline']['exit_code'] == 0 for c in cases),
              'all_compatibility_passed': all(c['compatibility']['exit_code'] == 0 for c in cases),
              'scope': 'CPU diagnostic compatibility only; no physical acceptance'}
    target = ROOT / 'work/_shared/lead-validation005.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'assignments': len(batch['assignments']), 'cases': len(cases),
                      'report': str(target.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
