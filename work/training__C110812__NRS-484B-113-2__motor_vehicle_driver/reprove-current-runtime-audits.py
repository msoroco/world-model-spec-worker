"""Run selected delivery and comparison audits after all current-runtime chains."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = f'work/{HERE.name}/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(script, arguments, label, expected_code, expected_text):
    path = HERE/f'current-runtime-{label}.log'
    command = [sys.executable, str(HERE/script), *arguments]
    with path.open('w') as stream:
        code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
    if code != expected_code or expected_text not in path.read_text():
        raise RuntimeError(f'{label} audit failed; see {path}')
    return {'command': f'.venv-cpu/bin/python {PREFIX}{script} '+' '.join(arguments),
            'exit_code': code, 'log': path.name, 'sha256': sha(path)}


def main():
    progress = json.loads((HERE/'current-runtime-matrix-progress.json').read_text())
    if progress['completed'] != 12 or len(progress['rows']) != 12:
        raise ValueError('All twelve candidate chains must pass before independent audits')
    results = {'format': 'c110812-current-runtime-independent-audits-v1',
               'runtime_manifest_sha256': progress['runtime_manifest_sha256'], 'delivery': [], 'comparisons': []}
    for suffix in ('false', 'true', 'control'):
        target = HERE/f'current-runtime-{suffix}-primary-result.json'
        if suffix != 'control':
            locations = sorted((ROOT/'.runtime-work').glob(f'c110812-current-runtime-{suffix}-primary-saved-*/output/v0001/analysis/result.json'))
            if len(locations) != 1:
                raise ValueError('Expected exactly one saved result for '+suffix)
            shutil.copyfile(locations[0], target)
        if not target.is_file():
            raise ValueError('Primary saved result missing: '+suffix)
        script = 'audit-lawful-control.py' if suffix == 'control' else 'audit-selected-delivery.py'
        case_id = f'{HERE.name}__{suffix}'
        common = ['--case', case_id]
        positive = execute(script, common, f'delivery-{suffix}-positive', 0, '"passed": true')
        negative_flag = '--drop-native' if suffix == 'control' else '--remove-native-source'
        negative = execute(script, [*common, negative_flag], f'delivery-{suffix}-negative', 1,
                           'Missing required source: native_samples.jsonl')
        results['delivery'].append({'suffix': suffix, 'result_sha256': sha(target),
                                    'positive': positive, 'negative': negative})
    for pair, script in (('straight-corner', 'audit-selected-comparison.py'),
                         ('control', 'audit-control-comparison.py')):
        positive = execute(script, [], f'comparison-{pair}-positive', 0, '"passed": true')
        negative = execute(script, ['--reject-comparison-drift'],
                           f'comparison-{pair}-negative-drift', 1,
                           'Comparison fixed condition changed: primary')
        missing = execute(script, ['--remove-native-source'],
                          f'comparison-{pair}-negative-missing-source', 1,
                          'Missing required source: native_samples.jsonl')
        results['comparisons'].append({'pair': pair, 'positive': positive,
                                       'negative_drift': negative, 'negative_missing_source': missing})
    path = HERE/'current-runtime-independent-audits.json'
    path.write_text(json.dumps(results, indent=2)+'\n')
    print('three delivery and two comparison audits passed with negative controls')


if __name__ == '__main__':
    main()
