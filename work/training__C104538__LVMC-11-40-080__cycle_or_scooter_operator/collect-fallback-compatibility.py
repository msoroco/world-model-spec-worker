"""Retain exact positive and missing-source public fallback CPU receipts."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = ROOT / '.runtime-work' / ('c104538-compat-fallback' + suffix[-1])
        receipt = json.loads((source / 'compatibility.json').read_text())
        candidate = entry['candidates'][0]
        if (not receipt['passed'] or receipt['case_id'] != entry['case_id'] or
                receipt['candidate_id'] != 'fallback1' or
                receipt['construction_sha256'] != candidate['construction_sha256']):
            raise ValueError('Fallback compatibility identity changed: ' + suffix)
        target = HERE / 'selected-proof' / suffix / 'fallback1'
        target.mkdir(parents=True, exist_ok=True)
        names = ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log')
        for name in names:
            shutil.copyfile(source / name, target / name)
        candidate['compatibility'] = {
            'receipt': str((target / 'compatibility.json').relative_to(HERE)),
            'sha256': sha(target / 'compatibility.json'),
            'log': str((target / 'compatibility-analysis.log').relative_to(HERE)),
            'negative_log': str((target / 'negative-analysis.log').relative_to(HERE)),
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
