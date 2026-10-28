"""Fresh lead CPU validation of every exact assignment case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime/main-pipeline-v1'
VALIDATOR = ROOT / '.runtime-work/decoder-v3/.lake/build/bin/adapterCheck'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    with log.open('x') as output:
        proc = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                              text=True)
    return {'command': command, 'exit_code': proc.returncode,
            'log': str(log.relative_to(ROOT)), 'sha256': digest(log)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', required=True)
    args = parser.parse_args()
    output = ROOT / '.runtime-work' / args.prefix
    output.mkdir(parents=True, exist_ok=False)
    logs = ROOT / 'work/_shared/lead-logs'
    logs.mkdir(parents=True, exist_ok=True)
    batch = json.loads((ROOT / 'batch.json').read_text())
    cases = []
    for aid in batch['assignments']:
        folder = ROOT / 'work' / aid
        manifest = folder / 'execution-manifest.json'
        entries = json.loads(manifest.read_text())['cases']
        for entry in entries:
            case = entry['case_id']
            case_output = output / case
            case_output.mkdir()
            fixture_name = entry.get('compatibility', {}).get('fixture')
            if fixture_name:
                fixture = ROOT / fixture_name
            else:
                fixture = folder / 'fixture-diagnostic'
            offline = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(manifest), '--case', case,
                       '--output', str(case_output / 'offline')]
            compatibility = [str(PYTHON), str(ROOT / 'runtime.py'), 'compatibility',
                             '--manifest', str(manifest), '--case', case,
                             '--fixture', str(fixture), '--output', str(case_output / 'compatibility'),
                             '--library', str(RUNTIME / 'library'), '--validator', str(VALIDATOR)]
            record = {'assignment_id': aid, 'case_id': case,
                      'offline': run(offline, logs / (args.prefix + '.' + case + '.offline.log'))}
            materialized = case_output / 'offline/config.json'
            if materialized.exists():
                preflight = [str(PYTHON), '-m', 'worker_exchange.atom_preflight',
                             '--runtime', str(RUNTIME), '--config', str(materialized)]
                env = dict(__import__('os').environ)
                env['PYTHONPATH'] = str(RUNTIME / 'scenario_pipeline')
                preflight_log = logs / (args.prefix + '.' + case + '.preflight.log')
                with preflight_log.open('x') as stream:
                    checked = subprocess.run(preflight, cwd=ROOT, env=env, stdout=stream,
                                             stderr=subprocess.STDOUT, text=True)
                record['atom_preflight'] = {'command': preflight, 'exit_code': checked.returncode,
                                             'log': str(preflight_log.relative_to(ROOT)),
                                             'sha256': digest(preflight_log)}
            record['compatibility'] = run(compatibility,
                                          logs / (args.prefix + '.' + case + '.compatibility.log'))
            receipt = case_output / 'compatibility/compatibility.json'
            if receipt.is_file():
                record['compatibility_receipt_sha256'] = digest(receipt)
            cases.append(record)
            print(len(cases), case, flush=True)
    report = {'format': 'fresh-lead-exact-case-validation-v1', 'cases': cases,
              'all_offline_passed': all(c['offline']['exit_code'] == 0 for c in cases),
              'all_atom_preflight_passed': all(c.get('atom_preflight', {}).get('exit_code') == 0 for c in cases),
              'all_compatibility_passed': all(c['compatibility']['exit_code'] == 0 for c in cases),
              'scope': 'CPU software compatibility only; no CARLA or physical acceptance'}
    target = ROOT / 'work/_shared/lead-validation.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'assignments': len(batch['assignments']), 'cases': len(cases),
                      'offline_passed': sum(c['offline']['exit_code'] == 0 for c in cases),
                      'compatibility_passed': sum(c['compatibility']['exit_code'] == 0 for c in cases)}))


if __name__ == '__main__':
    main()
