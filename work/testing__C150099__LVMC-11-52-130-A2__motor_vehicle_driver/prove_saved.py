"""Exercise recorded-only processing on ten case-specific synthetic sources."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args: str) -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
    run = subprocess.run([str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                          *map(str, args)], cwd=REPO, env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if run.returncode:
        raise ValueError(run.stdout[-1400:])


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    # Materialize every source before adding proof metadata to the manifest.
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        source = REPO / '.runtime-work' / ('c150099-saved-source-' + suffix + '-v7')
        fixture = REPO / '.runtime-work' / ('c150099-saved-fixture-' + suffix + '-v7')
        if source.exists() or fixture.exists():
            raise ValueError('choose fresh saved-source version: ' + suffix)
        command('materialize', '--manifest', MANIFEST, '--case', entry['case_id'],
                '--output', source)
        command('fixture', '--recipe', REPO / entry['fixture_recipe'], '--output', fixture)
        for path in fixture.iterdir():
            destination = source / path.name
            if destination.exists():
                raise ValueError('fixture shadows materialized source: ' + path.name)
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        source = REPO / '.runtime-work' / ('c150099-saved-source-' + suffix + '-v7')
        output = REPO / '.runtime-work' / ('c150099-saved-proof-' + suffix + '-v7')
        command('process-saved', '--manifest', MANIFEST, '--case', entry['case_id'],
                '--attempt', source, '--output', output, '--library',
                REPO / 'runtime/library', '--validator',
                REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck')
        receipt = output / 'v0001/processing.json'
        saved = ROOT / ('cpu-saved-' + suffix + '.json')
        shutil.copyfile(receipt, saved)
        proof = json.loads(saved.read_text())
        if (proof['passed'] is not True or proof['recorded_only'] is not True or
                proof['originals_preserved'] is not True or
                proof['case_id'] != entry['case_id']):
            raise ValueError('saved-only proof incomplete: ' + suffix)
        entry['saved_diagnostic'] = {'receipt': saved.name, 'sha256': sha(saved),
                                     'source': str(source.relative_to(REPO)),
                                     'physical_acceptance_claimed': False}
        print('saved-only passed:', suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
