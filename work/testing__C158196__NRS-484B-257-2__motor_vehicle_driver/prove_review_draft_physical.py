"""Renew physical outcome fixtures against the staged camera-review bundles."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'review-draft-manifest.json'
DEST = ROOT / 'review-draft/draft-physical-proofs'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    manifest = json.loads(MANIFEST.read_text())
    receipts = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = ROOT / entry['construction']
        officer = 'officer-reference' in source.name
        script = ROOT / ('prove_officer_reference_physical.py' if officer else 'physical_fixture_proof.py')
        fixtures = []
        for kind in KINDS:
            folder = DEST / suffix / kind
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(script), '--case-suffix', suffix,
                       '--kind', kind, '--construction', str(source),
                       '--output', str(folder)]
            log = folder / 'proof.log'
            env = os.environ.copy()
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=REPO, env=env,
                                           stdout=stream, stderr=subprocess.STDOUT,
                                           timeout=120, check=False)
            result = folder / 'result.json'
            if completed.returncode or not result.is_file():
                raise SystemExit('Physical fixture failed: ' + suffix + ' ' + kind)
            check = json.loads(result.read_text())['physical_checks']['maneuver']['status']
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if check != expected:
                raise SystemExit('Physical outcome differed: ' + suffix + ' ' + kind)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': completed.returncode,
                             'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(ROOT)),
                             'result_sha256': sha(result)})
        old_lifecycle = (ROOT / 'cases' / (suffix + '-officer-reference-lifecycle.log')
                         if officer else ROOT / 'cases' / (suffix + '-physical-proofs/lifecycle.log'))
        if not old_lifecycle.is_file():
            raise SystemExit('Original lifecycle proof missing: ' + suffix)
        receipt = {'format': 'c158196-review-draft-physical-preparation',
                   'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                 'exit_code': 0,
                                 'log': str(old_lifecycle.relative_to(ROOT)),
                                 'log_sha256': sha(old_lifecycle)}}
        receipt_path = DEST / suffix / 'receipt.json'
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        receipts.append({'case_id': entry['case_id'],
                         'construction_sha256': entry['construction_sha256'],
                         'receipt': str(receipt_path.relative_to(ROOT)),
                         'sha256': sha(receipt_path)})
        print(suffix, 'passed', flush=True)
    (DEST / 'index.json').write_text(json.dumps({
        'format': 'c158196-review-draft-physical-index',
        'manifest_sha256': sha(MANIFEST), 'receipts': receipts}, indent=2) + '\n')


if __name__ == '__main__':
    main()
