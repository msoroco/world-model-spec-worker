"""Rebuild source-bound physical classifier fixtures for draft primaries."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'body-geometry-all-draft-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 8:
        raise ValueError('Expected eight exact case primaries')
    output_root = ROOT / 'body-geometry-draft' / 'physical-proofs'
    for case in manifest['cases']:
        case_id = case['case_id']
        label = case_id.rsplit('source_verified_', 1)[1]
        folder = output_root / label
        folder.mkdir(parents=True, exist_ok=True)
        saved = REPO / '.runtime-work/c101303-body-geometry-all-saved-v1' / (
            'source_verified_' + label + '-primary/v0001/processing.json')
        saved_copy = folder / 'primary-saved-processing.json'
        shutil.copyfile(saved, saved_copy)
        processing = json.loads(saved_copy.read_text())
        if (processing.get('passed') is not True or
                processing['analysis_revision']['construction_sha256']
                != case['construction_sha256']):
            raise ValueError('Draft primary saved receipt is not exact: ' + label)
        receipt = {'format': 'worker-physical-preparation-fixtures',
                   'case_id': case_id,
                   'construction_sha256': case['construction_sha256'],
                   'diagnostic_fixture': True,
                   'physical_acceptance_claimed': False,
                   'fixtures': []}
        for kind in (*KINDS, 'lifecycle'):
            target = folder / (kind + '.json')
            command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'physical_fixture_proof.py'),
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--kind', kind, '--output', str(target)]
            if kind == 'lifecycle':
                command.extend(['--saved-receipt', str(saved_copy)])
            completed = subprocess.run(command, cwd=REPO, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = folder / (kind + '.log')
            log.write_text(completed.stdout)
            if completed.returncode:
                raise ValueError('Draft physical fixture failed: ' + label + '/' + kind)
            if kind == 'lifecycle':
                events = json.loads(target.read_text())['events']
                receipt['lifecycle'] = {'events': events, 'exit_code': 0,
                                        'log': str(log.relative_to(ROOT)),
                                        'log_sha256': digest(log),
                                        'fixture_receipt': str(target.relative_to(ROOT))}
            else:
                receipt['fixtures'].append({
                    'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                    'log': str(log.relative_to(ROOT)), 'log_sha256': digest(log),
                    'result': str(target.relative_to(ROOT)),
                    'result_sha256': digest(target)})
        receipt_path = folder / 'receipt.json'
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        print(label, 'three outcomes and lifecycle passed', flush=True)


if __name__ == '__main__':
    main()
