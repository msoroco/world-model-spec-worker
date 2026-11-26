import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)

for entry in manifest['cases']:
    suffix = entry['case_id'].removeprefix(HERE.name + '__')
    candidate = entry['candidates'][0]
    assert candidate['id'] == 'fallback1'
    offline = REPO / '.runtime-work' / f'c129273-offline-{suffix}-fallback1-v8'
    compat = REPO / '.runtime-work' / f'c129273-compat-{suffix}-fallback1-v8'
    offline_log = HERE / 'offline' / f'{suffix}-fallback1.log'
    compat_receipt = HERE / 'compatibility' / f'{suffix}-fallback1.json'
    compat_log = HERE / 'compatibility' / f'{suffix}-fallback1-analysis.log'
    negative_log = HERE / 'compatibility' / f'{suffix}-fallback1-negative.log'
    copy(offline / 'offline.log', offline_log)
    copy(compat / 'compatibility.json', compat_receipt)
    copy(compat / 'compatibility-analysis.log', compat_log)
    copy(compat / 'negative-analysis.log', negative_log)
    receipt = json.loads(compat_receipt.read_text())
    assert receipt['passed'] is True
    assert receipt['case_id'] == entry['case_id']
    assert receipt['candidate_id'] == 'fallback1'
    assert receipt['construction_sha256'] == candidate['construction_sha256']
    assert receipt['log_sha256'] == sha(compat_log)
    assert receipt['negative_log_sha256'] == sha(negative_log)
    candidate['offline'] = {
        'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --candidate fallback1 --output .runtime-work/c129273-offline-{suffix}-fallback1-v8',
        'exit_code': 0,
        'construction_sha256': candidate['construction_sha256'],
        'log': str(offline_log.relative_to(HERE)),
        'log_sha256': sha(offline_log),
    }
    candidate['compatibility'] = {
        'receipt': str(compat_receipt.relative_to(HERE)),
        'sha256': sha(compat_receipt),
        'log': str(compat_log.relative_to(HERE)),
        'negative_log': str(negative_log.relative_to(HERE)),
    }
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('fallbacks_bound', len(manifest['cases']), sha(manifest_path))
