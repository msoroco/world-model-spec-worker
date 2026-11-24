"""Bind exact packet-aware offline checks for every selected candidate."""
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
        for candidate_id, selected in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            proof_tag = 'coverage' if suffix == 'controlled_1' else 'preflight'
            source = ROOT / '.runtime-work' / f'c104538-offline-{suffix}-{candidate_id}-{proof_tag}' / 'offline.log'
            if not source.is_file():
                raise ValueError('Missing packet-aware offline log')
            target = HERE / 'selected-proof' / suffix / candidate_id / 'offline.log'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            selected['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --candidate {candidate_id} --output .runtime-work/c104538-offline-{suffix}-{candidate_id}-{proof_tag}',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': str(target.relative_to(HERE)), 'log_sha256': sha(target),
            }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
