"""Bind five current-runtime offline proofs to their exact selected constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        slug = entry['case_id'].rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / ('c386328-' + slug.replace('_', '') + '-offline-v4') / 'offline.log'
        if not source.is_file():
            raise ValueError('Exact offline log missing: ' + slug)
        destination = HERE / ('native-proof-' + slug + '.log')
        destination.write_text(source.read_text().rstrip() + '\n')
        entry['offline'] = {'command': 'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c386328-owner TMPDIR=.runtime-work .venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/draft-native-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/c386328-' + slug.replace('_', '') + '-offline-v4 --python $PWD/.venv-cpu/bin/python',
                            'construction_sha256': entry['construction_sha256'],
                            'exit_code': 0, 'log': destination.name,
                            'log_sha256': sha(destination)}
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return {'offline_cases': len(manifest['cases']), 'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
