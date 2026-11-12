"""Bind verified opposite-case diagnostic receipts into the delivery manifest."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__off_opposite_left_turn'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    main_path = HERE / 'execution-manifest.json'
    main = json.loads(main_path.read_text())
    candidate = json.loads((HERE / 'opposite-candidate-manifest.json').read_text())
    entry = next(row for row in candidate['cases'] if row['case_id'] == CASE)
    if any(row['case_id'] == CASE for row in main['cases']):
        raise ValueError('Opposite case already bound; retain current receipts')
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        selected = entry if ident == 'primary' else next(
            row for row in entry['candidates'] if row['id'] == ident)
        construction_sha = sha(HERE / selected['construction'])
        if construction_sha != selected['construction_sha256']:
            raise ValueError('Changed opposite construction: ' + ident)
        tag = 'opposite-' + ident
        offline_log = HERE / (tag + '-offline-v1.log')
        if '"offline_passed": true' not in offline_log.read_text():
            raise ValueError('Exact offline proof missing: ' + ident)
        command = ('.venv-cpu/bin/python runtime.py offline --manifest '
                   f'work/{HERE.name}/opposite-candidate-manifest.json --case {CASE} ')
        if ident != 'primary':
            command += f'--candidate {ident} '
        command += f'--output .runtime-work/c125697-{tag}-offline-v1'
        selected['offline'] = {'command': command, 'exit_code': 0,
                               'construction_sha256': construction_sha,
                               'log': offline_log.name, 'log_sha256': sha(offline_log)}
        attempt = REPO / f'.runtime-work/c125697-{tag}-compatibility-v1'
        names = {'receipt': tag + '-compatibility-receipt.json',
                 'log': tag + '-compatibility-analysis.log',
                 'negative': tag + '-negative-analysis.log'}
        for source, target in [('compatibility.json', names['receipt']),
                               ('compatibility-analysis.log', names['log']),
                               ('negative-analysis.log', names['negative'])]:
            shutil.copyfile(attempt / source, HERE / target)
        receipt_file = HERE / names['receipt']
        receipt = json.loads(receipt_file.read_text())
        turn = receipt['measurement_examples']['opposite_left_turn_context']['value']
        if (receipt.get('passed') is not True or receipt['case_id'] != CASE or
                receipt['candidate_id'] != ident or
                receipt['construction_sha256'] != construction_sha or
                receipt['log_sha256'] != sha(HERE / names['log']) or
                receipt['negative_log_sha256'] != sha(HERE / names['negative']) or
                turn['observed_heading_deg'] != [180, 270] or
                turn['exception_judgment'] != 'unresolved'):
            raise ValueError('Opposite source receipt mismatch: ' + ident)
        saved = json.loads((HERE / f'{tag}-saved-v1.log').read_text())
        if (saved.get('passed') is not True or
                saved.get('recorded_only') is not True or
                saved.get('originals_preserved') is not True or
                saved.get('physical_acceptance_claimed') is not False or
                saved.get('case_id') != CASE or
                saved.get('candidate_id') != ident):
            raise ValueError('Opposite recorded-only saved proof missing: ' + ident)
        selected['compatibility'] = {'receipt': names['receipt'],
                                     'sha256': sha(receipt_file),
                                     'log': names['log'],
                                     'negative_log': names['negative']}
    entry['negative'] = {'log': 'opposite-primary-negative-analysis.log'}
    main['cases'].append(entry)
    main['status'] = 'partial_five_case_opposite_source_diagnostic'
    main_path.write_text(json.dumps(main, indent=2, allow_nan=False) + '\n')
    return {'case_id': CASE, 'constructions': 4,
            'primary_sha256': entry['construction_sha256']}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
