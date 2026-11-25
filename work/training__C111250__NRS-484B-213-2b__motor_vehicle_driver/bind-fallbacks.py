"""Bind final-hash lower-speed fallback preflight and public receipts."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target.relative_to(FOLDER).as_posix()


def main():
    path = FOLDER / 'selected-probe-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        fallback = entry['candidates'][0]
        prefix = f'c111250-selected-{suffix}-fallback1'
        compat = SCRATCH / f'{prefix}-compat'
        proof = FOLDER / 'selected-proofs'
        receipt = FOLDER / copy(compat / 'compatibility.json', proof / f'{suffix}-fallback1-compatibility.json')
        log = FOLDER / copy(compat / 'compatibility-analysis.log', proof / f'{suffix}-fallback1-analysis.log')
        negative = FOLDER / copy(compat / 'negative-analysis.log', proof / f'{suffix}-fallback1-negative.log')
        offline = FOLDER / copy(SCRATCH / f'{prefix}-offline.log', proof / f'{suffix}-fallback1-offline.log')
        result = json.loads(receipt.read_text())
        if (not result['passed'] or result['candidate_id'] != 'fallback1' or
                result['construction_sha256'] != fallback['construction_sha256'] or
                result['log_sha256'] != sha(log) or result['negative_log_sha256'] != sha(negative)):
            raise ValueError('Fallback proof differs from selected construction')
        fallback['offline'] = {'command':
            f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/selected-probe-manifest.json --case {entry["case_id"]} --candidate fallback1 --output .runtime-work/{prefix}-offline --python $PWD/.venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': fallback['construction_sha256'],
            'log': offline.relative_to(FOLDER).as_posix(), 'log_sha256': sha(offline)}
        fallback['compatibility'] = {'receipt': receipt.relative_to(FOLDER).as_posix(),
                                     'sha256': sha(receipt), 'log': log.relative_to(FOLDER).as_posix(),
                                     'negative_log': negative.relative_to(FOLDER).as_posix()}
        print(suffix, sha(receipt))
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
