"""Bind current exact CPU receipts after the complete-body measurement repair."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = (
    ('left', 'off_ego_left_near_time', True),
    ('right', 'off_ego_right_near_time', True),
    ('separated', 'off_ego_left_separated', True),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    bound = []
    first = next(row for row in manifest['cases'] if row['case_id'].endswith('__off_ego_left_near_time'))
    for label, suffix, fallbacks in SUFFIXES:
        case = HERE.name+'__'+suffix
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        if label == 'separated':
            entry['acquisition'] = first['acquisition']
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3') if fallbacks else ('primary',):
            selected = entry if ident == 'primary' else next(c for c in entry['candidates'] if c['id'] == ident)
            tag = label+'-'+ident
            construction_sha = sha(HERE/selected['construction'])
            if construction_sha != selected['construction_sha256']:
                raise ValueError(f'{tag} construction changed')
            offline_log = HERE/f'{tag}-complete-body-offline-v1.log'
            if '"offline_passed": true' not in offline_log.read_text():
                raise ValueError(f'{tag} exact offline failed')
            selected['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {case} '+('' if ident == 'primary' else f'--candidate {ident} ')+f'--output .runtime-work/c125697-{tag}-complete-body-offline-v1',
                'exit_code': 0, 'construction_sha256': construction_sha,
                'log': offline_log.name, 'log_sha256': sha(offline_log),
            }
            attempt = REPO/f'.runtime-work/c125697-{tag}-complete-body-compatibility-v1'
            files = {
                'receipt': ('compatibility.json', f'{tag}-complete-body-compatibility-receipt.json'),
                'log': ('compatibility-analysis.log', f'{tag}-complete-body-analysis.log'),
                'negative_log': ('negative-analysis.log', f'{tag}-complete-body-negative.log'),
            }
            for source, destination in files.values():
                shutil.copyfile(attempt/source, HERE/destination)
            receipt_path = HERE/files['receipt'][1]
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get('passed') is not True or receipt.get('case_id') != case
                    or receipt.get('candidate_id') != ident
                    or receipt.get('construction_sha256') != construction_sha
                    or receipt.get('log_sha256') != sha(HERE/files['log'][1])
                    or receipt.get('negative_log_sha256') != sha(HERE/files['negative_log'][1])):
                raise ValueError(f'{tag} compatibility source receipt changed')
            if label == 'separated':
                timing = receipt['measurement_examples']['entry_timing']['value']
                if (abs(timing['absolute_difference_s']-1.4) > .001
                        or timing['first_complete_body_entry']['ego']['frame'] != 164
                        or timing['first_complete_body_entry']['other']['frame'] != 192):
                    raise ValueError('Separated complete-body timing differs from original source')
            selected['compatibility'] = {
                'receipt': receipt_path.name, 'sha256': sha(receipt_path),
                'log': files['log'][1],
            }
            if ident == 'primary':
                selected['negative'] = {'log': files['negative_log'][1]}
            else:
                selected['compatibility']['negative_log'] = files['negative_log'][1]
            bound.append(tag)
    manifest['status'] = 'partial_three_case_complete_body_diagnostic'
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'bound': bound}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
