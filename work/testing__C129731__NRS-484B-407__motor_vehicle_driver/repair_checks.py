"""Rebind three scoped QA repairs and rerun every exact CPU compatibility case."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
IDS = [
    'testing__C144550__NRS-484B-223-1b__motor_vehicle_driver',
    'testing__C109749__NRS-484B-253__motor_vehicle_driver',
]
PY = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime/main-pipeline-v1'
ENV = dict(os.environ, PYTHONPATH=str(RUNTIME / 'scenario_pipeline'))
DECODER = REPO / '.runtime-work/decoder-v3/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def run(command, log, env=ENV):
    command = [str(x) for x in command]
    result = subprocess.run(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout)
    print(log.relative_to(REPO), result.returncode, flush=True)
    if result.returncode:
        print(result.stdout[-5000:], flush=True)
        raise RuntimeError('Command failed: ' + ' '.join(command))
    return {'command': ' '.join(command), 'exit_code': 0,
            'log': str(log.relative_to(log.parents[1])), 'sha256': sha(log)}


for aid in IDS:
    folder = REPO / 'work' / aid
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if not (folder / 'build_package.py').exists():
        for source in [folder / 'construction.json'] + [folder / case['construction'] for case in manifest['cases']]:
            construction = json.loads(source.read_text())
            for item in construction['files']:
                if item['path'] in ('runner.py', 'analyze.py', 'tests/test_scenario.py'):
                    item['content'] = (folder / item['path']).read_text()
            write(source, construction)
        for entry in manifest['cases']:
            entry['construction_sha256'] = sha(folder / entry['construction'])
            entry.pop('compatibility', None)
    result_path = folder / 'result.json'
    result = json.loads(result_path.read_text())
    result['tests'] = []
    result['compatibility_attempts'] = []
    write(manifest_path, manifest)
    unit = [PY, '-m', 'unittest', 'discover', '-s', folder / 'tests', '-p', 'test_*.py', '-v']
    unit_env = dict(ENV, PYTHONPATH=str(folder) + os.pathsep + ENV['PYTHONPATH'])
    result['tests'].append(run(unit, folder / 'tests/qa-repair-unit.log', unit_env))
    for number, entry in enumerate(manifest['cases']):
        case = entry['case_id']
        suffix = case.split('__')[-1]
        bundle = json.loads((folder / entry['construction']).read_text())
        config = next(item['content'] for item in bundle['files'] if item['path'] == 'config.json')
        config_file = REPO / '.runtime-work/qa-repair-preflight' / (case + '.json')
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(config)
        preflight = [PY, '-m', 'worker_exchange.atom_preflight', '--runtime', RUNTIME,
                     '--config', config_file]
        result['tests'].append(run(preflight, folder / 'tests' / (suffix + '.qa-preflight.log')))
        base = REPO / '.runtime-work/qa-repair-final-v3' / (aid + '-' + suffix)
        offline = [PY, REPO / 'runtime.py', 'offline', '--manifest', manifest_path,
                   '--case', case, '--output', str(base) + '-offline']
        result['tests'].append(run(offline, folder / 'tests' / (suffix + '.qa-offline.log')))
        output = Path(str(base) + '-compat')
        compat = [PY, REPO / 'runtime.py', 'compatibility', '--manifest', manifest_path,
                  '--case', case, '--fixture', folder / 'fixture-diagnostic', '--output', output,
                  '--library', RUNTIME / 'library', '--validator', DECODER]
        attempt = run(compat, folder / 'tests' / (suffix + '.qa-compatibility.log'))
        receipt = folder / 'compatibility' / (suffix + '.qa.json')
        analysis_log = folder / 'compatibility' / (suffix + '.qa.analysis.log')
        receipt.parent.mkdir(exist_ok=True)
        shutil.copyfile(output / 'compatibility.json', receipt)
        shutil.copyfile(output / 'compatibility-analysis.log', analysis_log)
        entry['compatibility'] = {'receipt': str(receipt.relative_to(folder)), 'sha256': sha(receipt),
                                  'fixture': str((folder / 'fixture-diagnostic').relative_to(REPO)),
                                  'log': str(analysis_log.relative_to(folder))}
        attempt.update({'case_id': case, 'receipt': str(receipt.relative_to(folder)),
                        'receipt_sha256': sha(receipt)})
        result['compatibility_attempts'].append(attempt)
        write(manifest_path, manifest)
    result['physical_acceptance'] = False
    result['reason'] = 'All exact cases pass repaired package measurements and pinned software compatibility; native motion, geometry, visibility, public-way authority and legal judgment remain unverified.'
    write(result_path, result)
    print('completed', aid, len(manifest['cases']), flush=True)
