"""Prove the exception and official draft constructions on the active runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c405647-1a-runtime-import')
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    output = HERE / 'current-other-offline'
    output.mkdir(exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c405647-1a-other-') as temp:
        for branch in ('exception', 'official'):
            manifest = HERE / branch / 'package-manifest.json'
            data = json.loads(manifest.read_text())
            for case in data['cases']:
                suffix = case['case_id'].rsplit('__', 1)[1]
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                    ref = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
                    construction = HERE / branch / ref['construction']
                    if sha(construction) != ref['construction_sha256']:
                        raise ValueError('Construction hash differs: ' + str(construction))
                    destination = Path(temp) / f'{suffix}-{candidate}'
                    command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline', '--manifest', str(manifest),
                               '--case', case['case_id'], '--candidate', candidate, '--output', str(destination),
                               '--python', str(PYTHON)]
                    result = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, timeout=300)
                    command_log = output / f'{suffix}-{candidate}-command.log'
                    command_log.write_text(result.stdout.rstrip() + '\n')
                    unit = destination / 'offline.log'
                    unit_log = output / f'{suffix}-{candidate}-offline.log'
                    if unit.is_file():
                        unit_log.write_text(unit.read_text().rstrip() + '\n')
                    row = {'case_id': case['case_id'], 'candidate_id': candidate,
                           'construction_sha256': ref['construction_sha256'], 'exit_code': result.returncode,
                           'command_log': command_log.relative_to(HERE).as_posix(),
                           'command_log_sha256': sha(command_log),
                           'offline_log': unit_log.relative_to(HERE).as_posix() if unit_log.is_file() else None,
                           'offline_log_sha256': sha(unit_log) if unit_log.is_file() else None,
                           'simulation_started': False}
                    rows.append(row)
                    print(suffix, candidate, result.returncode, flush=True)
                    if result.returncode:
                        raise ValueError(f'Current offline failure {suffix} {candidate}: {result.stdout[-1000:]}')
    summary = {'format': 'c405647-1a-current-other-offline-v1', 'runtime_manifest_sha256':
               sha(ROOT / 'runtime/SOURCE-MANIFEST.json') if (ROOT / 'runtime/SOURCE-MANIFEST.json').is_file() else None,
               'passed': True, 'case_count': 4, 'candidate_count': len(rows), 'rows': rows,
               'scope': 'CPU-only draft preflight, no Native execution'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
