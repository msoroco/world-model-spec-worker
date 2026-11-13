"""Return exact physical and lifecycle CPU proof artifacts for staged signal cases."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'signal-distance-draft-manifest.json'
SCRIPT = ROOT / 'inside_physical_fixture_proof.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.physical_preparation import validate as validate_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=60)
    log.write_text(process.stdout + process.stderr)
    if process.returncode != 0:
        raise ValueError('Physical fixture failed: ' + ' '.join(command) + '\n' + process.stderr[-3000:])
    return process


def main():
    cases = json.loads(MANIFEST.read_text())['cases']
    bound = []
    for entry in cases:
        case = entry['case_id']
        label = 'below' if entry['signal_target_m'] == 25.0 else 'above'
        folder = ROOT / 'cases' / case.rsplit('__', 1)[1] / 'physical-proofs'
        folder.mkdir(exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in KINDS:
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT),
                       '--manifest', str(MANIFEST), '--case', case,
                       '--kind', kind, '--output', str(output)]
            if kind == 'lifecycle':
                saved = (REPO / '.runtime-work' /
                         f'c109749-signal-distance-{label}-primary-saved-v5/v0001/processing.json')
                command.extend(['--saved-receipt', str(saved)])
            run(command, log)
            row = {'command': ' '.join(str(part) for part in command),
                   'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                   'log_sha256': sha(log), 'result': str(output.relative_to(ROOT)),
                   'result_sha256': sha(output)}
            if kind == 'lifecycle':
                lifecycle = dict(row, events=json.loads(output.read_text())['events'])
            else:
                fixtures.append(dict(row, kind=kind))
        receipt = {'format': 'worker-physical-preparation', 'case_id': case,
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures, 'lifecycle': lifecycle}
        path = folder / 'receipt.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        check = dict(entry, physical_preparation={
            'receipt': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        validate_physical(REPO, ROOT, check)
        bound.append({'case_id': case, 'receipt': str(path.relative_to(ROOT)),
                      'receipt_sha256': sha(path),
                      'fixture_kinds': [row['kind'] for row in fixtures],
                      'lifecycle_events': lifecycle['events']})
    if len(bound) != 2:
        raise ValueError('Both exact signal cases need physical receipts')
    print(json.dumps({'format': 'worker-signal-distance-returned-physical-proof',
                      'cases': bound, 'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
