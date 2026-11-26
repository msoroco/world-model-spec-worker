"""Retain six current-runtime selected construction offline receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c230259-nrs213'
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = ROOT / 'selected-construction-draft.json'
    entries = json.loads(manifest.read_text())['cases']
    if [entry['case_id'].split('__')[-1] for entry in entries] != list(SUFFIXES):
        raise ValueError('Selected construction inventory changed')
    proofs = []
    for suffix, entry in zip(SUFFIXES, entries):
        source = ROOT / entry['construction']
        if sha(source) != entry['construction_sha256']:
            raise ValueError('Selected exact construction changed: ' + suffix)
        log = SCRATCH / ('selected-offline-v3-' + suffix) / 'offline.log'
        raw = log.read_text()
        if 'OK' not in raw or 'Ran 4 tests' not in raw:
            raise ValueError('Selected offline not passing: ' + suffix)
        target = ROOT / 'native' / ('selected-' + suffix + '-offline.log')
        target.write_text(raw.rstrip() + '\n')
        proofs.append({'case_id': entry['case_id'], 'construction_sha256': sha(source),
                       'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ROOT.name +
                                  '/selected-construction-draft.json --case ' + entry['case_id'] +
                                  ' --output .runtime-work/c230259-nrs213/selected-offline-v3-' + suffix,
                       'exit_code': 0, 'log': str(target.relative_to(ROOT)),
                       'log_sha256': sha(target), 'tests': 4})
    result = {'format': 'worker-selected-offline-draft-proof-v1',
              'assignment_id': ROOT.name, 'manifest_sha256': sha(manifest),
              'cases': proofs, 'native_executed': False,
              'compatibility_proved': False, 'delivery_ready': False}
    target = ROOT / 'native/selected-offline-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'count': len(proofs), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
