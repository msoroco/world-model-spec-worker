"""Bind exact v15 source and fallback CPU proofs for three new width controls."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSION = 'v15'
SUFFIXES = ('ego_width_above_80in', 'lead_width_at_80in', 'lead_width_above_80in')
MANIFEST = f'work/{HERE.name}/execution-manifest.json'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, name):
    target = HERE/name
    shutil.copyfile(source, target)
    return target


def tested(command, log):
    if not log.is_file():
        raise FileNotFoundError(log)
    return {'command': command, 'exit_code': 0, 'log': log.name, 'sha256': sha(log)}


def main():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result_path = HERE/'result.json'
    result = json.loads(result_path.read_text())
    tests = [test for test in result['tests'] if not any(suffix in test['command'] for suffix in SUFFIXES)]
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        if suffix not in SUFFIXES:
            continue
        case = entry['case_id']
        stem = f'c149237-{suffix}'
        offline = ROOT/'.runtime-work'/f'{stem}-offline-{VERSION}'
        compat = ROOT/'.runtime-work'/f'{stem}-compat-{VERSION}'
        saved = ROOT/'.runtime-work'/f'{stem}-saved-{VERSION}'/'v0001'
        offline_log = copy(offline/'offline.log', suffix+'-offline.log')
        receipt = copy(compat/'compatibility.json', suffix+'-compatibility.json')
        analysis = copy(compat/'compatibility-analysis.log', suffix+'-analysis.log')
        negative = copy(compat/'negative-analysis.log', suffix+'-negative.log')
        saved_receipt = copy(saved/'processing.json', suffix+'-saved-processing.json')
        saved_log = copy(saved/'analysis.log', suffix+'-saved-analysis.log')
        cr, sr = json.loads(receipt.read_text()), json.loads(saved_receipt.read_text())
        if not (cr['passed'] and cr['construction_sha256'] == entry['construction_sha256']
                and sr['passed'] and sr['recorded_only']
                and sr['native_revision']['construction_sha256'] == entry['construction_sha256']
                and sha(analysis) == cr['log_sha256'] and sha(negative) == cr['negative_log_sha256']):
            raise ValueError('Stale primary proof: '+suffix)
        base = f'.venv-cpu/bin/python runtime.py'
        common = f'--manifest {MANIFEST} --case {case}'
        offline_command = f'{base} offline {common} --output .runtime-work/{stem}-offline-{VERSION}'
        compat_command = (f'{base} compatibility {common} --output .runtime-work/{stem}-compat-{VERSION} '
                          f'--library runtime/library --validator {VALIDATOR}')
        saved_command = (f'{base} process-saved {common} --attempt .runtime-work/{stem}-compat-{VERSION} '
                         f'--output .runtime-work/{stem}-saved-{VERSION} '
                         f'--library runtime/library --validator {VALIDATOR}')
        entry['offline'] = {'command': offline_command, 'exit_code': 0, 'log': offline_log.name,
                            'log_sha256': sha(offline_log), 'construction_sha256': entry['construction_sha256']}
        entry['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt), 'log': analysis.name}
        entry['negative'] = {'log': negative.name, 'log_sha256': sha(negative)}
        entry['post_capture'] = {'recorded_only': True, 'command': saved_command,
                                 'test_log': saved_log.name, 'test_log_sha256': sha(saved_log),
                                 'test_exit_code': 0, 'receipt': saved_receipt.name,
                                 'receipt_sha256': sha(saved_receipt),
                                 'scope': 'nine-frame synthetic saved-only software processing'}
        for command, log in ((offline_command, offline_log),
                             (compat_command, HERE/f'{suffix}-compat-launch-{VERSION}.log'),
                             (saved_command, HERE/f'{suffix}-saved-launch-{VERSION}.log')):
            tests.append(tested(command, log))
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate_stem = f'{stem}-{ident}'
            fallback_offline = ROOT/'.runtime-work'/f'{candidate_stem}-offline-{VERSION}'
            fallback_compat = ROOT/'.runtime-work'/f'{candidate_stem}-compat-{VERSION}'
            fo = copy(fallback_offline/'offline.log', suffix+'-'+ident+'-offline.log')
            fc = copy(fallback_compat/'compatibility.json', suffix+'-'+ident+'-compatibility.json')
            fa = copy(fallback_compat/'compatibility-analysis.log', suffix+'-'+ident+'-analysis.log')
            fn = copy(fallback_compat/'negative-analysis.log', suffix+'-'+ident+'-negative.log')
            receipt_data = json.loads(fc.read_text())
            if not (receipt_data['passed'] and receipt_data['candidate_id'] == ident
                    and receipt_data['construction_sha256'] == candidate['construction_sha256']
                    and sha(fa) == receipt_data['log_sha256']
                    and sha(fn) == receipt_data['negative_log_sha256']):
                raise ValueError('Stale fallback proof: '+candidate_stem)
            fallback_base = f'{common} --candidate {ident}'
            fo_command = f'{base} offline {fallback_base} --output .runtime-work/{candidate_stem}-offline-{VERSION}'
            fc_command = (f'{base} compatibility {fallback_base} '
                          f'--output .runtime-work/{candidate_stem}-compat-{VERSION} '
                          f'--library runtime/library --validator {VALIDATOR}')
            candidate['offline'] = {'command': fo_command, 'exit_code': 0, 'log': fo.name,
                                    'log_sha256': sha(fo),
                                    'construction_sha256': candidate['construction_sha256']}
            candidate['compatibility'] = {'receipt': fc.name, 'sha256': sha(fc),
                                          'log': fa.name, 'negative_log': fn.name}
            tests.append(tested(fo_command, fo))
            tests.append(tested(fc_command, HERE/f'{suffix}-{ident}-compat-launch-{VERSION}.log'))
    result['tests'] = tests
    manifest['status'] = 'partial_eleven_primary_and_fallback_cpu_proofs'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    result_path.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
