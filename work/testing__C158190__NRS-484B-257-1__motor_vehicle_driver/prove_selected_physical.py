"""Bind five selected physical classifier/lifecycle CPU fixture receipts."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SUMMARY = HERE / 'selected-saved-proof-summary.json'
OUTPUT = HERE / 'physical-proofs'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def prove():
    old_manifest = MANIFEST.read_bytes()
    manifest = json.loads(old_manifest)
    summary = json.loads(SUMMARY.read_text())
    if summary['manifest_sha256'] != sha(MANIFEST) or len(manifest['cases']) != 5:
        raise ValueError('Selected saved-proof summary differs from current five-case manifest')
    rows = {(x['case_id'], x['candidate_id']): x for x in summary['results']}
    updates = []
    for entry in manifest['cases']:
        case = entry['case_id']
        label = case.rsplit('__', 1)[-1]
        source = rows[(case, 'primary')]
        compatibility_receipt = REPO / source['compatibility']
        attempt = compatibility_receipt.parent
        saved = REPO / source['processing']
        if sha(compatibility_receipt) != source['compatibility_sha256']:
            raise ValueError('Current primary compatibility receipt changed: ' + label)
        if sha(saved) != source['processing_sha256']:
            raise ValueError('Current selected saved receipt changed: ' + label)
        if json.loads(saved.read_text())['analysis_revision']['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Selected saved receipt binds another construction: ' + label)
        folder = OUTPUT / label
        folder.mkdir(parents=True, exist_ok=True)
        local_saved = folder / 'primary-saved-processing.json'
        shutil.copy2(saved, local_saved)
        receipt = {'format': 'worker-physical-preparation-fixtures', 'case_id': case,
                   'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                   'saved_processing_sha256': sha(local_saved), 'fixtures': []}
        for kind in KINDS:
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            args = ['.venv-cpu/bin/python', str((HERE / 'physical_fixture_proof.py').relative_to(REPO)),
                    '--manifest', str(MANIFEST.relative_to(REPO)), '--case', case,
                    '--source', str(attempt.relative_to(REPO)), '--kind', kind,
                    '--output', str(output.relative_to(REPO)),
                    '--saved-receipt', str(local_saved.relative_to(REPO))]
            with log.open('w') as stream:
                subprocess.run(args, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)
            record = {'kind': kind, 'command': ' '.join(args), 'exit_code': 0,
                      'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                      'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)}
            if kind == 'lifecycle':
                record['events'] = json.loads(output.read_text())['events']
                receipt['lifecycle'] = record
            else:
                receipt['fixtures'].append(record)
        path = folder / 'receipt.json'
        write(path, receipt)
        updates.append((entry, path))
    for entry, path in updates:
        entry['physical_preparation'] = {'receipt': str(path.relative_to(HERE)), 'sha256': sha(path)}
    write(MANIFEST, manifest)
    return {'case_count': len(updates), 'fixture_count': len(updates) * len(KINDS),
            'manifest_sha256': sha(MANIFEST), 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
