"""Rerun selected CPU proofs against the current combined manifest snapshot."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = '.venv-cpu/bin/python'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with (HERE / log).open('w') as output:
        result = subprocess.run(command, cwd=REPO, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{log}: exit {result.returncode}')


def main():
    manifest = HERE / 'execution-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    index = {'format': 'worker-c125763-canonical-manifest-snapshot-proofs',
             'manifest': 'execution-manifest.json', 'manifest_sha256': sha(manifest),
             'status': 'partial_snapshot', 'cases': [],
             'rerun_if_manifest_changes': True, 'physical_acceptance_claimed': False}
    for prefix, entry in zip(('primary', 'right', 'separated', 'opposite'), entries):
        case = entry['case_id']
        stem = f'canonical-promoted-{prefix}-acquisition'
        output = f'.runtime-work/c125763-{stem}'
        compat_log = stem + '-compat.log'
        run([PYTHON, 'runtime.py', 'compatibility', '--manifest', str(manifest.relative_to(REPO)),
             '--case', case, '--output', output + '-compat', '--library', 'runtime/library',
             '--validator', VALIDATOR], compat_log)
        receipt = json.loads((REPO / (output + '-compat') / 'compatibility.json').read_text())
        if receipt['construction_sha256'] != entry['construction_sha256'] or not receipt['passed']:
            raise RuntimeError('Wrong canonical compatibility receipt: ' + case)
        compat_receipt = stem + '-compatibility-receipt.json'
        (HERE / compat_receipt).write_text(json.dumps(receipt, indent=2) + '\n')
        saved_log = stem + '-saved.log'
        run([PYTHON, 'runtime.py', 'process-saved', '--manifest', str(manifest.relative_to(REPO)),
             '--case', case, '--attempt', output + '-compat', '--output', output + '-saved',
             '--library', 'runtime/library', '--validator', VALIDATOR], saved_log)
        saved = json.loads((HERE / saved_log).read_text())
        if saved['analysis_revision']['construction_sha256'] != entry['construction_sha256'] or not saved['passed']:
            raise RuntimeError('Wrong canonical saved receipt: ' + case)
        saved_receipt = stem + '-saved-receipt.json'
        (HERE / saved_receipt).write_text(json.dumps(saved, indent=2) + '\n')
        index['cases'].append({'case_id': case, 'candidate_id': 'primary',
            'compatibility_receipt': compat_receipt, 'compatibility_sha256': sha(HERE / compat_receipt),
            'compatibility_log': compat_log, 'compatibility_log_sha256': sha(HERE / compat_log),
            'saved_receipt': saved_receipt, 'saved_sha256': sha(HERE / saved_receipt),
            'saved_log': saved_log, 'saved_log_sha256': sha(HERE / saved_log)})
        print(json.dumps({'case_id': case, 'canonical_compatibility': 'passed',
                          'canonical_saved': 'passed'}), flush=True)
    (HERE / 'canonical-proof-index.json').write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    main()
