"""Reprocess all exact cases against the stable aggregate manifest."""

import hashlib
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

from lifecycle_fixture import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'execution-manifest.json'
    before = sha(manifest)
    entries = json.loads(manifest.read_text())['cases']
    output = HERE / 'aggregate-saved'
    output.mkdir(exist_ok=True)
    proofs = []
    for entry in entries:
        case = entry['case_id']
        captured = StringIO()
        with redirect_stdout(captured):
            proof = run(case)
        if proof['manifest_sha256'] != before or not proof['passed'] or not proof['originals_preserved'] or proof['missing_evidence']:
            raise ValueError('Aggregate saved processing did not bind current manifest and originals: ' + case)
        path = output / (case.rsplit('__', 1)[-1] + '.json')
        log = output / (case.rsplit('__', 1)[-1] + '.log')
        log.write_text(captured.getvalue() + case + ' aggregate_manifest_saved_processing_passed\n')
        path.write_text(json.dumps(proof, indent=2) + '\n')
        proofs.append({'case_id': case, 'receipt': str(path.relative_to(HERE)),
                       'sha256': sha(path), 'log': str(log.relative_to(HERE)),
                       'log_sha256': sha(log)})
        print(case, 'aggregate_manifest_saved_processing_passed', flush=True)
    if sha(manifest) != before:
        raise ValueError('Aggregate execution manifest changed during saved reproof')
    (output / 'index.json').write_text(json.dumps({
        'format': 'worker-aggregate-saved-proof-index', 'assignment_id': HERE.name,
        'manifest_sha256': before, 'cases': proofs, 'diagnostic_fixture': True,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()
