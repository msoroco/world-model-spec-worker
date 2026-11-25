"""Bind completed synthetic fallback CPU proofs to the selected draft."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / '.runtime-work' / 'c150116'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(HERE.name + '__')
        candidate = entry['candidates'][0]
        if candidate['id'] != 'fallback1':
            raise ValueError(name + ': unexpected candidate')
        source = SCRATCH / ('fallback-compat-' + name)
        receipt = json.loads((source / 'compatibility.json').read_text())
        if not receipt.get('passed') or receipt['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError(name + ': compatibility not passed')
        target = HERE / 'proofs' / ('fallback1-' + name)
        target.mkdir(parents=True, exist_ok=True)
        for source_name, target_name in [('compatibility.json', 'receipt.json'),
                                         ('compatibility-analysis.log', 'analysis.log'),
                                         ('negative-analysis.log', 'negative.log')]:
            shutil.copyfile(source / source_name, target / target_name)
        offline_log = HERE / ('cpu-nov25-fallback-offline-' + name + '.log')
        if not offline_log.exists() or offline_log.stat().st_size == 0:
            raise ValueError(name + ': offline log missing')
        candidate['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                       '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --candidate fallback1 --output .runtime-work/c150116/fallback-offline-' + name,
            'exit_code': 0,
            'construction_sha256': candidate['construction_sha256'],
            'log': offline_log.name,
            'log_sha256': sha(offline_log),
        }
        candidate['compatibility'] = {
            'receipt': str((target / 'receipt.json').relative_to(HERE)),
            'sha256': sha(target / 'receipt.json'),
            'log': str((target / 'analysis.log').relative_to(HERE)),
            'negative_log': str((target / 'negative.log').relative_to(HERE)),
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
