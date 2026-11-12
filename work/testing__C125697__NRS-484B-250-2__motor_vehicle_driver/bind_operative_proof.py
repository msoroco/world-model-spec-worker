"""Bind exact operative construction and positive/negative diagnostic receipts."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__operative_signal'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    construction = HERE / entry['construction']
    construction_sha = sha(construction)
    if construction_sha != entry['construction_sha256']:
        raise ValueError('Operative construction changed')
    offline = HERE / 'operative-primary-offline-v2.log'
    if '"offline_passed": true' not in offline.read_text():
        raise ValueError('Exact operative offline proof missing')
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --output .runtime-work/c125697-operative-primary-offline-v2',
        'exit_code': 0, 'construction_sha256': construction_sha,
        'log': offline.name, 'log_sha256': sha(offline),
    }
    attempt = REPO / '.runtime-work/c125697-operative-primary-compatibility-v2'
    files = {'receipt': ('compatibility.json', 'operative-primary-compatibility-receipt.json'),
             'log': ('compatibility-analysis.log', 'operative-primary-compatibility-analysis.log'),
             'negative': ('negative-analysis.log', 'operative-primary-negative-analysis.log')}
    for source, target in files.values():
        shutil.copyfile(attempt / source, HERE / target)
    receipt_file = HERE / files['receipt'][1]
    receipt = json.loads(receipt_file.read_text())
    context = receipt['measurement_examples']['device_qualification_context']['value']
    if (receipt.get('passed') is not True or receipt['case_id'] != CASE or
            receipt['candidate_id'] != 'primary' or
            receipt['construction_sha256'] != construction_sha or
            receipt['log_sha256'] != sha(HERE / files['log'][1]) or
            receipt['negative_log_sha256'] != sha(HERE / files['negative'][1]) or
            context['ego_governing_state'] != 'Red' or
            context['other_governing_state'] != 'Green' or
            context['official_device_exclusion_judgment'] != 'unresolved'):
        raise ValueError('Operative source receipt does not match construction and signal state')
    entry['compatibility'] = {'receipt': receipt_file.name, 'sha256': sha(receipt_file),
                              'log': files['log'][1]}
    entry['negative'] = {'log': files['negative'][1]}
    for candidate in entry['candidates']:
        ident = candidate['id']
        tag = 'operative-' + ident
        candidate_sha = sha(HERE / candidate['construction'])
        if candidate_sha != candidate['construction_sha256']:
            raise ValueError('Operative fallback construction changed: ' + ident)
        offline_log = HERE / f'{tag}-offline-v1.log'
        if '"offline_passed": true' not in offline_log.read_text():
            raise ValueError('Operative fallback offline proof missing: ' + ident)
        candidate['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --candidate {ident} --output .runtime-work/c125697-{tag}-offline-v1',
            'exit_code': 0, 'construction_sha256': candidate_sha,
            'log': offline_log.name, 'log_sha256': sha(offline_log),
        }
        candidate_attempt = REPO / f'.runtime-work/c125697-{tag}-compatibility-v1'
        candidate_files = {
            'receipt': ('compatibility.json', f'{tag}-compatibility-receipt.json'),
            'log': ('compatibility-analysis.log', f'{tag}-compatibility-analysis.log'),
            'negative': ('negative-analysis.log', f'{tag}-negative-analysis.log'),
        }
        for source, target in candidate_files.values():
            shutil.copyfile(candidate_attempt / source, HERE / target)
        candidate_receipt_file = HERE / candidate_files['receipt'][1]
        candidate_receipt = json.loads(candidate_receipt_file.read_text())
        signal = candidate_receipt['measurement_examples']['device_qualification_context']['value']
        if (candidate_receipt.get('passed') is not True or
                candidate_receipt['case_id'] != CASE or
                candidate_receipt['candidate_id'] != ident or
                candidate_receipt['construction_sha256'] != candidate_sha or
                candidate_receipt['log_sha256'] != sha(HERE / candidate_files['log'][1]) or
                candidate_receipt['negative_log_sha256'] != sha(HERE / candidate_files['negative'][1]) or
                (signal['ego_governing_state'], signal['other_governing_state']) != ('Red', 'Green')):
            raise ValueError('Operative fallback source receipt mismatch: ' + ident)
        candidate['compatibility'] = {
            'receipt': candidate_receipt_file.name,
            'sha256': sha(candidate_receipt_file),
            'log': candidate_files['log'][1],
            'negative_log': candidate_files['negative'][1],
        }
    manifest['status'] = 'partial_four_case_operative_diagnostic'
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'case_id': CASE, 'construction_sha256': construction_sha,
            'compatibility_sha256': sha(receipt_file)}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
