"""Bind the selected ego-right case's exact, synthetic CPU receipts."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RIGHT = HERE.name+'__off_ego_right_near_time'
LEFT = HERE.name+'__off_ego_left_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == RIGHT)
    left = next(row for row in manifest['cases'] if row['case_id'] == LEFT)
    construction_sha = sha(HERE/entry['construction'])
    if construction_sha != entry['construction_sha256']:
        raise ValueError('Right construction changed after proof')
    offline_log = HERE/'right-offline-v2.log'
    if '"offline_passed": true' not in offline_log.read_text():
        raise ValueError('Right exact offline proof missing')
    attempt = REPO/'.runtime-work/c125697-right-compatibility-v2'
    receipt = json.loads((attempt/'compatibility.json').read_text())
    side = receipt['measurement_examples']['relative_right_side']['value']
    timing = receipt['measurement_examples']['entry_timing']['value']
    if (receipt.get('passed') is not True or receipt['case_id'] != RIGHT
            or receipt['candidate_id'] != 'primary'
            or receipt['construction_sha256'] != construction_sha
            or side['other_spatially_right_of_ego_approach'] is not False
            or side['signed_lateral_offset_m'] <= 1
            or timing['first_complete_body_entry']['ego']['frame'] >=
               timing['first_complete_body_entry']['other']['frame']):
        raise ValueError('Right-side comparison measurement is not source supported')
    for source, destination in (
            ('compatibility.json', 'right-compatibility-receipt.json'),
            ('compatibility-analysis.log', 'right-compatibility-analysis.log'),
            ('negative-analysis.log', 'right-negative-analysis.log')):
        shutil.copyfile(attempt/source, HERE/destination)
    if (receipt['log_sha256'] != sha(HERE/'right-compatibility-analysis.log') or
            receipt['negative_log_sha256'] != sha(HERE/'right-negative-analysis.log')):
        raise ValueError('Right positive/negative source logs differ')
    entry['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {RIGHT} --output .runtime-work/c125697-right-offline-v2',
        'exit_code': 0, 'construction_sha256': construction_sha,
        'log': offline_log.name, 'log_sha256': sha(offline_log),
    }
    entry['compatibility'] = {
        'receipt': 'right-compatibility-receipt.json',
        'sha256': sha(HERE/'right-compatibility-receipt.json'),
        'log': 'right-compatibility-analysis.log',
    }
    entry['negative'] = {'log': 'right-negative-analysis.log'}
    entry['acquisition'] = left['acquisition']
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': RIGHT, 'construction_sha256': construction_sha,
            'compatibility_receipt_sha256': entry['compatibility']['sha256']}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
