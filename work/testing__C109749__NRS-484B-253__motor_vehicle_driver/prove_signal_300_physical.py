"""Exercise 86/91.44/97 m draft CPU classifier and lifecycle paths."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'signal-300-at-draft-manifest.json'
SCRIPT = ROOT / 'inside_physical_fixture_proof.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sides', action='store_true')
    args = parser.parse_args()
    manifest_path = (ROOT / 'signal-300-sides-draft-manifest.json') if args.sides else MANIFEST
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest['cases']) == (2 if args.sides else 1)
    proofs = []
    for entry in manifest['cases']:
      case = entry['case_id']
      target = entry['signal_target_m']
      assert case.startswith(ROOT.name + '__signal_advance_300_')
      label = 'at' if target == 91.44 else str(int(target))
      saved_tag = 'v2' if label == 'at' else 'v1'
      saved = (REPO / '.runtime-work' /
               f'c109749-signal-300-{label}-primary-saved-{saved_tag}/v0001/processing.json')
      assert saved.is_file()
      for kind in KINDS:
        output = REPO / '.runtime-work' / f'c109749-signal-300-{label}-physical-{kind}-v1.json'
        command = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT),
                   '--manifest', str(manifest_path), '--case', case,
                   '--kind', kind, '--output', str(output)]
        if kind == 'lifecycle':
            command.extend(['--saved-receipt', str(saved)])
        run = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=60)
        if run.returncode:
            raise ValueError('Exact physical/lifecycle CPU path failed: '
                             + ' '.join(command) + '\n' + run.stderr[-3000:])
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
            if (status != expected or result['physical_acceptance_claimed'] is not False
                    or result['diagnostic_fixture'] is not True):
                raise ValueError('Physical classifier outcome differs')
        proofs.append({'case_id': case, 'kind': kind, 'result_sha256': sha(output),
                       'source_kind': 'synthetic diagnostic',
                       'construction_sha256': entry['construction_sha256']})
    assert len(proofs) == 4 * len(manifest['cases'])
    print(json.dumps({'format': 'worker-signal-300-physical-lifecycle-proof',
                      'manifest_sha256': sha(manifest_path), 'proofs': proofs,
                      'physical_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
