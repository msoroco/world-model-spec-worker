"""Run exact staged signal cases through three physical outcomes and lifecycle."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'signal-distance-draft-manifest.json'
SCRIPT = ROOT / 'inside_physical_fixture_proof.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    proofs = []
    for entry in manifest['cases']:
        case = entry['case_id']
        label = 'below' if entry['signal_target_m'] == 25.0 else 'above'
        for kind in KINDS:
            output = REPO / '.runtime-work' / f'c109749-signal-distance-{label}-physical-{kind}.json'
            command = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT),
                       '--manifest', str(MANIFEST), '--case', case,
                       '--kind', kind, '--output', str(output)]
            if kind == 'lifecycle':
                saved = (REPO / '.runtime-work' /
                         f'c109749-signal-distance-{label}-primary-saved-v5/v0001/processing.json')
                command.extend(['--saved-receipt', str(saved)])
            run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=60)
            if run.returncode != 0:
                raise ValueError('Physical/lifecycle CPU proof failed: ' +
                                 ' '.join(command) + '\n' + run.stderr[-3000:])
            result = json.loads(output.read_text())
            if kind == 'lifecycle':
                if result['events'] != ['capture_finished', 'encoders_closed',
                                        'restoration_verified', 'native_exit',
                                        'owner_released', 'saved_processing_started']:
                    raise ValueError('Lifecycle order differs')
            else:
                status = result['physical_checks']['maneuver']['status']
                expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                            'missing_evidence': 'unverified'}[kind]
                if status != expected or result['physical_acceptance_claimed'] is not False:
                    raise ValueError('Physical outcome differs')
            proofs.append({'case_id': case, 'kind': kind,
                           'result_sha256': sha(output), 'result_path': str(output.relative_to(REPO)),
                           'construction_sha256': entry['construction_sha256']})
    if len(proofs) != 8:
        raise ValueError('Two cases times four physical/lifecycle paths required')
    print(json.dumps({'format': 'worker-signal-distance-physical-lifecycle-proof',
                      'proofs': proofs, 'source_kind': 'synthetic software diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
