"""Bind the 4 m/s candidate's existing pinned offline and compatibility proofs."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FOLDER = HERE / 'cases/through_mid'
MANIFEST = HERE / 'mid-speed-compatibility-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest['cases'][0]
    case = entry['case_id']
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        source = REPO / '.runtime-work' / (
            'c158190-mid-compat-v1' if ident == 'primary' else
            f'c158190-mid-{ident}-compat-v1')
        target = FOLDER if ident == 'primary' else FOLDER / 'fallbacks'
        prefix = '' if ident == 'primary' else ident + '-'
        receipt = target / (prefix + 'compatibility.json')
        log = target / (prefix + 'compatibility-analysis.log')
        negative = target / (prefix + 'negative-analysis.log')
        for name, output in (('compatibility.json', receipt),
                             ('compatibility-analysis.log', log),
                             ('negative-analysis.log', negative)):
            shutil.copyfile(source / name, output)
        proof = json.loads(receipt.read_text())
        selected = entry if ident == 'primary' else next(c for c in entry['candidates'] if c['id'] == ident)
        if not proof['passed'] or proof['candidate_id'] != ident or proof['case_id'] != case:
            raise ValueError('Compatibility receipt selected another candidate')
        if proof['construction_sha256'] != selected['construction_sha256']:
            raise ValueError('Compatibility receipt construction hash changed')
        selected['compatibility'] = {
            'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt),
            'log': str(log.relative_to(HERE)), 'negative_log': str(negative.relative_to(HERE)),
            'replay_command': '.venv-cpu/bin/python runtime.py compatibility --manifest '
                              f'work/{HERE.name}/mid-speed-compatibility-manifest.json '
                              f'--case {case} --candidate {ident} '
                              f'--output .runtime-work/c158190-mid-{ident}-compat-v1 '
                              '--library runtime/library '
                              '--validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck',
        }
        if ident != 'primary':
            offline_log = target / (ident + '-offline.log')
            selected['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           f'work/{HERE.name}/mid-speed-compatibility-manifest.json '
                           f'--case {case} --candidate {ident} '
                           f'--output .runtime-work/c158190-mid-{ident}-offline-v1',
                'exit_code': 0,
                'log': str(offline_log.relative_to(HERE)),
                'log_sha256': sha(offline_log),
                'construction_sha256': selected['construction_sha256'],
            }
    entry['negative'] = {'log': 'cases/through_mid/negative-analysis.log'}
    manifest['cases'][0] = entry
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'compatibility_receipts': 4,
                      'fallback_offline_receipts': 3,
                      'selected_delivery_manifest_changed': False}))


if __name__ == '__main__':
    main()
