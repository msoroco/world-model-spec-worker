"""Assemble the nine exact construction receipts without weakening their bindings."""

import argparse
import hashlib
import json
from pathlib import Path


SOURCES = (
    'vehicle-indicator-manifest.json',
    'vehicle-no-indicator-manifest.json',
    'clearance-wide-manifest.json',
    'clearance-narrow-manifest.json',
    'ped-no-horn-manifest.json',
    'ped-horn-manifest.json',
    'both-signals-manifest.json',
    'both-indicator-only-manifest.json',
    'hand-signal-manifest.json',
)


def assemble(folder):
    folder = Path(folder)
    plan = json.loads((folder / 'case-plan.json').read_text())
    assignment = plan['assignment_id']
    expected = {case['case_id'] for case in plan['cases']}
    entries = []
    runtime_hash = None
    for name in SOURCES:
        manifest = json.loads((folder / name).read_text())
        if (manifest.get('format'), manifest.get('assignment_id')) != (
                'worker-execution-manifest', assignment):
            raise ValueError('Individual manifest has wrong identity: ' + name)
        if runtime_hash is None:
            runtime_hash = manifest['runtime_manifest_sha256']
        elif manifest.get('runtime_manifest_sha256') != runtime_hash:
            raise ValueError('Individual manifests bind different runtimes')
        if len(manifest.get('cases', [])) != 1:
            raise ValueError('Individual manifest must contain one exact case: ' + name)
        entry = manifest['cases'][0]
        construction = (folder / entry['construction']).resolve()
        if not construction.is_relative_to(folder.resolve()):
            raise ValueError('Exact construction escapes assignment directory: ' + name)
        if not construction.is_file() or hashlib.sha256(
                construction.read_bytes()).hexdigest() != entry['construction_sha256']:
            raise ValueError('Exact construction source changed: ' + name)
        entries.append(entry)
    actual = [entry['case_id'] for entry in entries]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Nine-case plan and exact manifest identities differ')
    return {'format': 'worker-execution-manifest',
            'assignment_id': assignment,
            'runtime_manifest_sha256': runtime_hash,
            'cases': entries}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or args.folder / 'execution-manifest.json'
    output.write_text(json.dumps(assemble(args.folder), indent=2) + '\n')


if __name__ == '__main__':
    main()
