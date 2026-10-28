"""Run every partition-02 materialized case through the pinned CPU checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
IDS = json.loads((ROOT / 'partitions/demo-test-02.json').read_text())['assignment_ids']
PYTHON = ROOT / '.venv-cpu/bin/python'
DECODER = ROOT / '.runtime-work/decoder-v3/.lake/build/bin/adapterCheck'
ENV = dict(os.environ, PYTHONPATH=str(ROOT / 'runtime/main-pipeline-v1/scenario_pipeline'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(command, log, env=ENV):
    completed = subprocess.run([str(part) for part in command], cwd=ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout)
    print(str(log.relative_to(ROOT)), completed.returncode, flush=True)
    if completed.returncode:
        print(completed.stdout[-4000:], flush=True)
        raise RuntimeError('failed: ' + ' '.join(map(str, command)))
    return {'command': ' '.join(str(part.relative_to(ROOT)) if isinstance(part, Path) and part.is_relative_to(ROOT) else str(part) for part in command),
            'exit_code': completed.returncode, 'log': str(log.relative_to(log.parents[1])),
            'sha256': digest(log)}


for assignment_id in IDS:
    package = ROOT / 'work' / assignment_id
    manifest_path = package / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result = {'assignment_id': assignment_id,
              'input_sha256': digest(ROOT / 'inputs' / assignment_id / 'assignment.json'),
              'status': 'ready' if assignment_id.endswith(('250-1__motor_vehicle_driver', '250-2__motor_vehicle_driver')) else 'partial',
              'readiness_kind': 'capability', 'applied_update': 1, 'tests': [],
              'compatibility_attempts': [], 'physical_acceptance': False}
    for index, entry in enumerate(manifest['cases']):
        case_id = entry['case_id']
        label = case_id[len(assignment_id)+2:]
        construction = json.loads((package / entry['construction']).read_text())
        config_text = next(item['content'] for item in construction['files'] if item['path'] == 'config.json')
        config = ROOT / '.runtime-work' / 'p2-final-preflight' / (case_id + '.json')
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(config_text)
        preflight = [PYTHON, '-m', 'worker_exchange.atom_preflight', '--runtime',
                     ROOT / 'runtime/main-pipeline-v1', '--config', config]
        result['tests'].append(check(preflight, package / 'tests' / (label + '.preflight.log')))
        offline = [PYTHON, ROOT / 'runtime.py', 'offline', '--manifest', manifest_path,
                   '--case', case_id, '--output', ROOT / '.runtime-work' / 'p2-final-v2' / (label + '-' + assignment_id + '-offline')]
        result['tests'].append(check(offline, package / 'tests' / (label + '.offline.log')))
        output = ROOT / '.runtime-work' / 'p2-final-v2' / (label + '-' + assignment_id + '-compat')
        compatible = [PYTHON, ROOT / 'runtime.py', 'compatibility', '--manifest', manifest_path,
                      '--case', case_id, '--fixture', package / 'fixture-diagnostic', '--output', output,
                      '--library', ROOT / 'runtime/main-pipeline-v1/library', '--validator', DECODER]
        attempt = check(compatible, package / 'tests' / (label + '.compatibility.log'))
        receipt = package / 'compatibility' / (label + '.json')
        analysis_log = package / 'compatibility' / (label + '.analysis.log')
        receipt.parent.mkdir(exist_ok=True)
        shutil.copyfile(output / 'compatibility.json', receipt)
        shutil.copyfile(output / 'compatibility-analysis.log', analysis_log)
        entry['compatibility'] = {'receipt': str(receipt.relative_to(package)), 'sha256': digest(receipt),
                                  'fixture': str((package / 'fixture-diagnostic').relative_to(ROOT)),
                                  'log': str(analysis_log.relative_to(package))}
        attempt.update({'case_id': case_id, 'receipt': str(receipt.relative_to(package)),
                        'receipt_sha256': digest(receipt)})
        result['compatibility_attempts'].append(attempt)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    result['reason'] = ('Every exact case passed pinned software compatibility. Native motion, full-body geometry, '
                        'source video duration and physical/legal conditions remain unverified.' if result['status'] == 'ready' else
                        'Every exact case passed pinned software compatibility; indispensable legal term adapter path '
                        'is absent in the pinned Core runtime. Native physical and legal findings remain unresolved.')
    result['unresolved_physical_checks'] = ['native route and actor-body trajectory', 'camera pixels and event duration',
                                             'synthetic public-way or authority status', 'law-specific conditions in case-plan.json']
    (package / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('completed', assignment_id, len(manifest['cases']), flush=True)
