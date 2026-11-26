"""Attach immutable CPU proof receipts to the selected package."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def integrate_compatibility(manifest):
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        for candidate, target in [('primary', entry), ('fallback1', entry['candidates'][0])]:
            source = ROOT / '.runtime-work' / f'c385967-compat5-{suffix}-{candidate}'
            receipt = json.loads((source / 'compatibility.json').read_text())
            if receipt.get('passed') is not True or receipt.get('candidate_id') != candidate:
                raise ValueError('Compatibility receipt not a selected positive')
            paths = {}
            for src, name in [('compatibility.json', 'compatibility.json'),
                              ('compatibility-analysis.log', 'compatibility-analysis.log'),
                              ('negative-analysis.log', 'negative.log')]:
                destination = HERE / f'selected-{suffix}-{candidate}-{name}'
                shutil.copyfile(source / src, destination)
                paths[name] = f'native/{destination.name}'
            target['compatibility'] = {
                'receipt': paths['compatibility.json'],
                'sha256': sha(HERE / Path(paths['compatibility.json']).name),
                'log': paths['compatibility-analysis.log'],
                'negative_log': paths['negative.log']}
        entry['negative']['log'] = entry['compatibility']['negative_log']
    write(FOLDER / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    integrate_compatibility(manifest)
    print(sha(FOLDER / 'execution-manifest.json'))
