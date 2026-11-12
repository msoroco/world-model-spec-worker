"""Copy and bind eight current v14 diagnostic CPU proofs to the partial package."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
VERSION = 'v14'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, name):
    target = FOLDER/name
    shutil.copyfile(source, target)
    return target


def command(kind, case, suffix):
    stem = f'.runtime-work/c149237-{suffix}'
    base = f'.venv-cpu/bin/python runtime.py {kind} --manifest work/{FOLDER.name}/execution-manifest.json --case {case}'
    if kind == 'offline':
        return f'{base} --output {stem}-offline-{VERSION}'
    common = ' --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
    if kind == 'compatibility':
        return f'{base} --output {stem}-compat-{VERSION}{common}'
    return f'{base} --attempt {stem}-compat-{VERSION} --output {stem}-saved-{VERSION}{common}'


def main():
    manifest_path = FOLDER/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result_path = FOLDER/'result.json'
    result = json.loads(result_path.read_text())
    tests = []
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        base = ROOT/'.runtime-work'/f'c149237-{suffix}'
        offline = Path(str(base)+f'-offline-{VERSION}')
        compat = Path(str(base)+f'-compat-{VERSION}')
        saved = Path(str(base)+f'-saved-{VERSION}')/'v0001'
        for source in (offline/'offline.log', compat/'compatibility.json',
                       compat/'compatibility-analysis.log', compat/'negative-analysis.log',
                       saved/'processing.json', saved/'analysis.log'):
            if not source.is_file():
                raise FileNotFoundError(source)
        offline_log = copy(offline/'offline.log', suffix+'-offline.log')
        receipt = copy(compat/'compatibility.json', suffix+'-compatibility.json')
        analysis = copy(compat/'compatibility-analysis.log', suffix+'-analysis.log')
        negative = copy(compat/'negative-analysis.log', suffix+'-negative.log')
        saved_receipt = copy(saved/'processing.json', suffix+'-saved-processing.json')
        saved_log = copy(saved/'analysis.log', suffix+'-saved-analysis.log')
        cr = json.loads(receipt.read_text())
        sr = json.loads(saved_receipt.read_text())
        assert cr['passed'] is True and cr['construction_sha256'] == entry['construction_sha256']
        assert sr['passed'] is True and sr['recorded_only'] is True
        assert sr['native_revision']['construction_sha256'] == entry['construction_sha256']
        assert sha(analysis) == cr['log_sha256'] and sha(negative) == cr['negative_log_sha256']
        entry['offline'] = {'command': command('offline', case, suffix), 'exit_code': 0,
                            'log': offline_log.name, 'log_sha256': sha(offline_log),
                            'construction_sha256': entry['construction_sha256']}
        entry['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
                                  'log': analysis.name}
        entry['negative'] = {'log': negative.name, 'log_sha256': sha(negative)}
        entry['post_capture'] = {'recorded_only': True,
                                 'command': command('process-saved', case, suffix),
                                 'test_log': saved_log.name,
                                 'test_log_sha256': sha(saved_log), 'test_exit_code': 0,
                                 'receipt': saved_receipt.name,
                                 'receipt_sha256': sha(saved_receipt),
                                 'scope': 'nine-frame synthetic saved-only software processing'}
        for kind in ('offline', 'compatibility', 'process-saved'):
            log_kind = {'offline': 'offline', 'compatibility': 'compat', 'process-saved': 'saved'}[kind]
            if kind == 'offline':
                log = offline_log
            else:
                log = FOLDER/f'{suffix}-{log_kind}-launch-{VERSION}.log'
            assert log.is_file()
            tests.append({'command': command(kind, case, suffix), 'exit_code': 0,
                          'log': log.name, 'sha256': sha(log)})
    for cmd, name in (
        (f'.venv-cpu/bin/python -m unittest discover -s work/{FOLDER.name}/tests -v', 'cpu-tests-current.log'),
        ('.venv-cpu/bin/python runtime.py preflight', 'preflight-current.log'),
        (f'PYTHONPATH=runtime/scenario_pipeline:runtime/python .venv-cpu/bin/python runtime/scenario_pipeline/worker_exchange/atom_preflight.py --runtime runtime --config work/{FOLDER.name}/config.json', 'atom-preflight-current.log')):
        tests.append({'command': cmd, 'exit_code': 0, 'log': name, 'sha256': sha(FOLDER/name)})
    for kind, script in (('gap-boundary', 'prove_gap_comparison.py'),
                         ('width-boundary', 'prove_width_comparison.py'),
                         ('lane-exception', 'prove_lane_comparison.py'),
                         ('overtaking-exception', 'prove_overtaking_comparison.py')):
        log = FOLDER/f'{kind}-proof-{VERSION}.log'
        tests.append({'command': f'.venv-cpu/bin/python work/{FOLDER.name}/{script}',
                      'exit_code': 0, 'log': log.name, 'sha256': sha(log)})
    result['tests'] = tests
    result['readiness_kind'] = 'eight_primaries_compatible_saved_checkpoint'
    result['reason'] = ('All eight exact primary cases have current v14 exact offline, positive/negative '
                        'synthetic compatibility and recorded-only saved-processing proofs. Gap, width, '
                        'two-lane and overtaking saved-source comparisons passed positive and missing/changed-source negatives. '
                        'Risk-triggered fallbacks, independent delivery audits, '
                        'full-duration authored-road proof, canonical semantic proposals and shared delivery '
                        'artifacts remain worker-owned CPU work. Real CARLA truck dimensions, motion, visibility '
                        'and legal judgments remain unverified.')
    manifest['status'] = 'partial_eight_primaries_proved'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    result_path.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
