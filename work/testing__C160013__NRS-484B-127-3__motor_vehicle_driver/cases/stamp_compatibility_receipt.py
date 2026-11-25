"""Retain the exact current-runtime compatibility receipt for one selected case."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, stage):
    manifest = json.loads(MANIFEST.read_text())
    suffix = 'entrant_can_occupy_gap' if label == 'wide' else 'entrant_cannot_occupy_gap'
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    output = PACKAGE / 'cases'
    names = {'receipt': 'compatibility.json', 'log': 'compatibility-analysis.log',
             'negative': 'negative-analysis.log'}
    retained = {}
    for key, name in names.items():
        source = stage / name
        target = output / (suffix + '-' + name)
        shutil.copyfile(source, target)
        retained[key] = 'cases/' + target.name
    entry['compatibility'] = {'receipt': retained['receipt'],
                              'sha256': sha(PACKAGE / retained['receipt']),
                              'log': retained['log']}
    entry['negative'] = {'log': retained['negative']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(label, 'compatibility receipt retained', entry['compatibility']['sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label', choices=('wide', 'narrow'))
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    run(args.label, args.stage)
